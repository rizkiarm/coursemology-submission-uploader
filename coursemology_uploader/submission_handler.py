"""Submission handling and answer submission logic."""

from __future__ import annotations

from pathlib import Path

from coursemology_py.api.course.answers import AnswerAPI
from coursemology_py.api.course.submissions import AssessmentSubmissionsAPI
from coursemology_py.models.common import JobSubmitted
from coursemology_py.models.course.assessment.answer_payloads import (
    ProgrammingAnswerPayload,
    ProgrammingFilePayload,
)
from coursemology_py.models.course.submissions import (
    AssessmentSubmission,
    ProgrammingAnswerInfo,
)
from coursemology_py.models.course.users import CourseUser
from tqdm import tqdm

from coursemology_uploader.coursemology_queries import get_question_answer, get_question_key
from coursemology_uploader.types import StudentInfo, SubmissionReport


def _read_file_content(filepath: Path) -> str:
    """Read file content as UTF-8 string.

    Args:
        filepath: Path to the file to read.

    Returns:
        File content as UTF-8 string.

    Raises:
        OSError: If file cannot be read.
        UnicodeDecodeError: If file is not valid UTF-8.
    """
    with open(filepath, "rb") as f:
        return f.read().decode("utf-8")


def submit_answer(
    answer_api: AnswerAPI,
    answer: ProgrammingAnswerInfo,
    content: str,
) -> JobSubmitted:
    """Submit a single programming file content to an answer.

    Args:
        answer_api: API bound to the submission.
        answer: Programming answer info containing file metadata.
        content: File content as UTF-8 string.

    Returns:
        A JobSubmitted representing the background grading job.

    Raises:
        ValueError: If answer has no files_attributes.
        IndexError: If answer files_attributes is empty.
    """
    if not answer.fields.files_attributes:
        raise ValueError(f"Answer {answer.id} has no files_attributes")

    file_info = answer.fields.files_attributes[0]
    payload = ProgrammingAnswerPayload(
        id=answer.id,
        files_attributes=[
            ProgrammingFilePayload(
                id=file_info.id,
                filename=file_info.filename,
                content=content,
            )
        ],
    )
    return answer_api.submit_answer(payload)


def _create_submission_report_entry() -> SubmissionReport:
    """Create an empty submission report entry.

    Returns:
        Initialized SubmissionReport with empty lists.
    """
    return SubmissionReport(
        student=None,
        errors=[],
        submitted=[],
        no_match=[],
        no_submission=[],
    )


def _process_user_files(
    fname: str,
    files: dict[str, Path],
    submissions_api: AssessmentSubmissionsAPI,
    fname_student_map: dict[str, CourseUser],
    user_submission_map: dict[int, AssessmentSubmission],
    file_question_map: dict[str, str],
    report: dict[str, SubmissionReport],
    no_submission_content: str,
) -> list[JobSubmitted]:
    """Process files for a single user and submit answers.

    Args:
        fname: User directory name / filename key.
        files: Mapping of filename to filepath for this user.
        fname_student_map: Mapping of filename key to CourseUser.
        user_submission_map: Mapping of CourseUser.id to AssessmentSubmission.
        file_question_map: Mapping of filename regex to question title.
        submissions_api: Assessment submissions API.
        report: Report dictionary to update.

    Returns:
        List of JobSubmitted for submitted files.
    """
    submission_jobs: list[JobSubmitted] = []
    report_entry = report[fname]

    # Check if student exists
    if fname not in fname_student_map:
        report_entry["errors"].append("No matching student found")
        return submission_jobs

    student = fname_student_map[fname]
    report_entry["student"] = StudentInfo(
        name=student.name,
        email=student.email,
        id=str(student.id),
    )

    # Check if submission exists
    if student.id not in user_submission_map:
        error_msg = f"No matching submission found for student {student.name} ({student.id})"
        report_entry["errors"].append(error_msg)
        return submission_jobs

    submission = user_submission_map[student.id]
    assert submission.id is not None, f"Submission for student {student.id} has no ID"

    submission_edit = submissions_api.edit(submission.id)
    answer_api = submissions_api.answer(submission.id)

    # Track which questions received submissions
    submitted_questions: set[str] = set()

    # Submit files
    for filename, filepath in files.items():
        question_key = get_question_key(filename, file_question_map)
        if not question_key:
            report_entry["no_match"].append(filename)
            continue

        question_title = file_question_map[question_key]
        try:
            answer = get_question_answer(submission_edit, question_title)
            content = _read_file_content(filepath)
            submission_job = submit_answer(answer_api, answer, content)
            submission_jobs.append(submission_job)
            submitted_questions.add(question_key)
            report_entry["submitted"].append(filename)
        except (ValueError, OSError, UnicodeDecodeError) as e:
            error_msg = f"Failed to submit {filename}: {e}"
            report_entry["errors"].append(error_msg)

    # Submit placeholder for questions with no matching files
    for question_key, question_title in file_question_map.items():
        if question_key not in submitted_questions:
            report_entry["no_submission"].append(question_title)
            try:
                answer = get_question_answer(submission_edit, question_title)
                submission_job = submit_answer(answer_api, answer, no_submission_content)
                submission_jobs.append(submission_job)
            except ValueError as e:
                error_msg = f"Failed to submit placeholder for {question_title}: {e}"
                report_entry["errors"].append(error_msg)

    return submission_jobs


def submit_answers(
    submissions_api: AssessmentSubmissionsAPI,
    user_files: dict[str, dict[str, Path]],
    fname_student_map: dict[str, CourseUser],
    user_submission_map: dict[int, AssessmentSubmission],
    file_question_map: dict[str, str],
    no_submission_content: str,
) -> tuple[list[JobSubmitted], dict[str, SubmissionReport]]:
    """Submit matched files for each student to their assessment submission.

    Args:
        submissions_api: Assessment submissions API.
        user_files: Mapping of user directory to filename -> path.
        fname_student_map: Mapping of filename key to CourseUser.
        user_submission_map: Mapping of CourseUser.id to AssessmentSubmission.
        file_question_map: Mapping of filename regex to question title.
        no_submission_content: Default content for questions with no submission.

    Returns:
        Tuple of (list of submitted jobs, submission report dictionary).
    """
    report: dict[str, SubmissionReport] = {}
    all_submission_jobs: list[JobSubmitted] = []

    for fname, files in tqdm(user_files.items(), desc="Processing users"):
        report[fname] = _create_submission_report_entry()

        jobs = _process_user_files(
            fname,
            files,
            submissions_api,
            fname_student_map,
            user_submission_map,
            file_question_map,
            report,
            no_submission_content,
        )
        all_submission_jobs.extend(jobs)

    # Sort report entries for consistency
    for data in report.values():
        # Student info doesn't need sorting (it's a single object)
        data["errors"].sort()
        data["submitted"].sort()
        data["no_match"].sort()
        data["no_submission"].sort()

    return all_submission_jobs, report
