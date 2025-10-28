"""Coursemology submission uploader core utilities.

This module supports:
- Batch download and extraction of student submissions.
- Mapping filenames to students and Coursemology answers.
- Submitting programming answers to a specific assessment.
"""

import re
from pathlib import Path

import click
import yaml
from coursemology_py.api.course.answers import AnswerAPI
from coursemology_py.api.course.assessments import AssessmentAPI
from coursemology_py.api.course.submissions import AssessmentSubmissionsAPI
from coursemology_py.client import CoursemologyClient
from coursemology_py.models.common import JobSubmitted
from coursemology_py.models.course.assessment.answer_payloads import ProgrammingAnswerPayload, ProgrammingFilePayload
from coursemology_py.models.course.assessment.categories import CategoryBasic
from coursemology_py.models.course.assessments import AssessmentListData
from coursemology_py.models.course.submissions import (
    AssessmentSubmission,
    ProgrammingAnswerInfo,
    QuestionInfo,
    SubmissionEditData,
)
from coursemology_py.models.course.users import CourseUser
from tqdm import tqdm

from coursemology_uploader.configs import (
    BatchDownloadConfig,
    NameUserMapConfig,
    load_config,
)
from coursemology_uploader.csv_utils import csv_to_map_multiple_values
from coursemology_uploader.downloader import download_files
from coursemology_uploader.extractor import extract_zip_files
from coursemology_uploader.scraper import filter_urls, scrape_directory_index

JOB_TIMEOUT_SECONDS = 3600  # 1 hour
# Wait time for Coursemology background jobs (force submit/unsubmit)


def perform_batch_download(config: BatchDownloadConfig) -> list[Path]:
    """Scrape a directory index, filter URLs, and download matching files.

    Args:
        config: Batch download configuration.

    Returns:
        List of downloaded file paths.
    """
    urls: list[str] = scrape_directory_index(
        config.base_url,
        config.basic_auth.username if config.basic_auth else None,
        config.basic_auth.password if config.basic_auth else None,
    )
    filtered_urls = filter_urls(urls, pattern=config.filter_pattern)
    return download_files(
        filtered_urls,
        config.destination,
        username=config.basic_auth.username if config.basic_auth else None,
        password=config.basic_auth.password if config.basic_auth else None,
    )


def load_fname_user_map(config: NameUserMapConfig) -> dict[str, dict[str, str]]:
    """Load filename-to-user mapping from a CSV.

    Args:
        config: CSV mapping configuration.

    Returns:
        Mapping from CSV key to a dict containing user name and email.
    """
    return csv_to_map_multiple_values(
        config.csv,
        key_column=config.key,
        value_columns=[config.name, config.email],
    )


def get_user_files(base_dir: Path, pattern: str) -> dict[str, dict[str, Path]]:
    """Group files by user directory.

    Args:
        base_dir: Base directory containing user subdirectories.
        pattern: Glob pattern to match files (e.g., '**/*.py').

    Returns:
        Mapping: { user_dir_name: { filename: filepath } }.
    """
    user_files: dict[str, dict[str, Path]] = {filepath.parent.name: {} for filepath in base_dir.glob(pattern)}
    for filepath in base_dir.glob(pattern):
        user_files[filepath.parent.name][filepath.name] = filepath
    return user_files


def get_fname_student_map(
    config: NameUserMapConfig, students: list[CourseUser], fname_user_map: dict[str, dict[str, str]]
) -> dict[str, CourseUser]:
    """Resolve filename keys to CourseUser records by email or name.

    Args:
        config: Mapping config indicating which CSV columns correspond to name/email.
        students: List of CourseUser objects from Coursemology.
        fname_user_map: Mapping from filename key to name/email data.

    Returns:
        Mapping from filename key to CourseUser. Unmatched entries are reported.
    """
    email_student_map = {s.email: s for s in students}
    name_student_map = {s.name: s for s in students}
    fname_student_map: dict[str, CourseUser] = {}
    for fname, student in fname_user_map.items():
        email = student[config.email]
        name = student[config.name]
        if email in email_student_map:
            fname_student_map[fname] = email_student_map[email]
        elif name in name_student_map:
            fname_student_map[fname] = name_student_map[name]
        else:
            print(f"Could not find student for fname {fname} with name {name} and email {email}")
    return fname_student_map


def get_student_submissions(
    submissions_api: AssessmentSubmissionsAPI, students: list[CourseUser]
) -> list[AssessmentSubmission]:
    """Fetch submissions belonging to the provided students.

    Args:
        submissions_api: API for the target assessment submissions.
        students: Students to include.

    Returns:
        List of AssessmentSubmission for the specified students.
    """
    submissions = submissions_api.index().submissions
    student_submissions = [s for s in submissions if s.course_user.id in [stu.id for stu in students]]
    return student_submissions


def get_category(assessment_api: AssessmentAPI, category_title: str) -> CategoryBasic:
    """Find an assessment category by its title.

    Args:
        assessment_api: Assessment API client.
        category_title: Title of the category.

    Returns:
        The matching category object.

    Raises:
        ValueError: If the category is not found.
    """
    categories = assessment_api.categories.index().categories
    for category in categories:
        if category.title == category_title:
            return category
    raise ValueError(f"Category with title '{category_title}' not found.")


def get_assessment(assessment_api: AssessmentAPI, category_id: int, assessment_title: str) -> AssessmentListData:
    """Find an assessment by title within a category.

    Args:
        assessment_api: Assessment API client.
        category_id: ID of the parent category.
        assessment_title: Target assessment title.

    Returns:
        The matching assessment object.

    Raises:
        ValueError: If the assessment is not found.
    """
    assessments = assessment_api.assessments.index(category_id).assessments
    for assessment in assessments:
        if assessment.title == assessment_title:
            return assessment
    raise ValueError(f"Assessment with title '{assessment_title}' not found in category ID {category_id}.")


def get_question_key(filename: str, file_question_map: dict[str, str]) -> str | None:
    """Return the regex key in file_answer_map that matches the filename.

    Args:
        filename: The filename to match.
        file_answer_map: Mapping of regex/string pattern to answer index.

    Returns:
        The matching pattern key, or None if no pattern matches.
    """
    for pattern in file_question_map.keys():
        match = re.match(pattern, filename)
        if match:
            return pattern
    return None


def get_question(questions: list[QuestionInfo], title: str) -> QuestionInfo:
    """Find a question by its title.

    Args:
        questions: List of QuestionInfo objects.
        title: Target question title.

    Returns:
        The matching QuestionInfo object.

    Raises:
        ValueError: If the question is not found.
    """
    for question in questions:
        if question.question_title == title:
            return question
    raise ValueError(f"Question with title '{title}' not found.")


def get_answer(answers: list[ProgrammingAnswerInfo], answer_id: int) -> ProgrammingAnswerInfo:
    """Find a programming answer by its ID.

    Args:
        answers: List of ProgrammingAnswerInfo objects.
        answer_id: Target answer ID.

    Returns:
        The matching ProgrammingAnswerInfo object.

    Raises:
        ValueError: If the answer is not found.
    """
    for answer in answers:
        if answer.id == answer_id:
            return answer
    raise ValueError(f"Answer with ID '{answer_id}' not found.")


def get_question_answer(submission_edit: SubmissionEditData, question_title: str) -> ProgrammingAnswerInfo:
    """Get the programming answer for a specific question title in a submission.

    Args:
        submission_edit: The editable assessment submission.
        question_title: The target question title.

    Returns:
        The corresponding QuestionInfo and ProgrammingAnswerInfo objects.

    Raises:
        ValueError: If the question or answer is not found.
    """
    question = get_question(submission_edit.questions, question_title)
    if question.answer_id is None:
        raise ValueError(f"Question '{question_title}' has no associated answer ID.")
    answer = get_answer(submission_edit.answers, question.answer_id)  # pyright: ignore[reportArgumentType]
    return answer


def submit_answer(answer_api: AnswerAPI, answer: ProgrammingAnswerInfo, content: str) -> JobSubmitted:
    """Submit a single programming file content to an answer.

    Args:
        answer_api: API bound to the submission.
        answer: Programming answer info containing file metadata.
        content: File content as UTF-8 string.

    Returns:
        A JobSubmitted representing the background grading job.
    """
    file_info = answer.fields.files_attributes[0]
    payload = ProgrammingAnswerPayload(
        id=answer.id,
        files_attributes=[ProgrammingFilePayload(id=file_info.id, filename=file_info.filename, content=content)],
    )
    return answer_api.submit_answer(payload)


def submit_answers(
    submissions_api: AssessmentSubmissionsAPI,
    user_files: dict[str, dict[str, Path]],
    fname_student_map: dict[str, CourseUser],
    user_submission_map: dict[int, AssessmentSubmission],
    file_question_map: dict[str, str],
) -> tuple[list[JobSubmitted], dict[str, dict[str, list[str]]]]:
    """Submit matched files for each student to their assessment submission.

    Args:
        submissions_api: Assessment submissions API.
        user_files: Mapping of user directory to filename -> path.
        fname_student_map: Mapping of filename key to CourseUser.
        user_submission_map: Mapping of CourseUser.id to AssessmentSubmission.
        filename_answer_map: Mapping of filename regex to answer index.

    Returns:
        List of submitted jobs (one per submitted file).
    """
    report: dict[str, dict[str, list[str]]] = {}
    submission_jobs: list[JobSubmitted] = []
    for fname, files in tqdm(user_files.items()):
        report[fname] = {"student": [], "errors": [], "submitted": [], "no_match": [], "no_submission": []}
        if fname not in fname_student_map:
            report[fname]["errors"].append("No matching student found")
            print(f"Skipping {fname} as no matching student found")
            continue
        student = fname_student_map[fname]
        report[fname]["student"] = [student.name, student.email, str(student.id)]
        if student.id not in user_submission_map:
            report[fname]["errors"].append(f"No matching submission found for student {student.name} ({student.id})")
            print(f"Skipping {fname} as no matching submission found for student {student.name} ({student.id})")
            continue
        submission = user_submission_map[student.id]
        assert submission.id is not None
        submission_edit = submissions_api.edit(submission.id)
        answer_api = submissions_api.answer(submission.id)
        # print(f"Submitting files for {fname} for student {student.name} ({student.id}) to submission {submission.id}")
        submitted_questions: list[str] = []
        for filename, filepath in files.items():
            question_key = get_question_key(filename, file_question_map)
            if not question_key:
                report[fname]["no_match"].append(filename)
                print(f"  Skipping file {filename} as no matching question found")
                continue
            question_title = file_question_map[question_key]
            answer = get_question_answer(submission_edit, question_title)
            # print(f"  Submitting file {filepath}")
            with open(filepath, "rb") as f:
                content = f.read()
                submission_job = submit_answer(answer_api, answer, content.decode("utf-8"))
                submission_jobs.append(submission_job)
            submitted_questions.append(question_key)
            report[fname]["submitted"].append(filename)

        for question_key, question_title in file_question_map.items():
            if question_key in submitted_questions:
                continue
            report[fname]["no_submission"].append(question_title)
            print(f"  Warning: did not submit any file for question '{file_question_map[question_key]}'")
            answer = get_question_answer(submission_edit, question_title)
            submission_job = submit_answer(answer_api, answer, "# No submission")
            submission_jobs.append(submission_job)

    for data in report.values():
        for v in data.values():
            v.sort()

    return submission_jobs, report


def run(config_path: Path) -> list[JobSubmitted]:
    """Main function.

    Reads configuration, optionally downloads/extracts submissions, resolves
    students and submissions, and uploads programming answers.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        List of JobSubmitted for all uploaded files.
    """
    config = load_config(config_path)

    if config.batch_download:
        downloaded_paths = perform_batch_download(config.batch_download)
        print(f"Downloaded files to: {downloaded_paths}")

        extracted_path = extract_zip_files(downloaded_paths, config.base_dir)
        print(f"Extracted files to: {extracted_path}")

        assert config.base_dir == extracted_path, "Base directory does not match extracted path."

    user_files = get_user_files(config.base_dir, config.file_pattern)
    print(f"Loaded files for {len(user_files)} users from {config.base_dir} matching pattern '{config.file_pattern}'.")

    client = CoursemologyClient()
    client.login(config.coursemology.username, config.coursemology.password)
    course_api = client.course(config.coursemology.course_id)
    print(f"Logged in to Coursemology as {config.coursemology.username} for course {config.coursemology.course_id}.")

    students = course_api.users.index_students().users
    fname_user_map = load_fname_user_map(config.fname_user_map)
    print(f"Loaded name-user mapping for {len(fname_user_map)} entries.")
    fname_student_map = get_fname_student_map(config.fname_user_map, students, fname_user_map)

    assessment_api = course_api.assessment
    category = get_category(assessment_api, config.coursemology.assessment_category)
    assessment = get_assessment(assessment_api, category.id, config.coursemology.assessment_title)
    print(f"Found assessment '{assessment.title}' in category '{category.title}'.")

    submissions_api = assessment_api.submissions(assessment.id)
    student_submissions = get_student_submissions(submissions_api, students)
    user_submission_map = {s.course_user.id: s for s in student_submissions}

    if any([s.workflow_state == "unstarted" for s in student_submissions]):
        print("Some submissions are in 'unstarted' state. Forcing submission...")
        submit_job = submissions_api.force_submit_all([s.course_user.id for s in student_submissions])
        client.jobs.wait_for_completion(submit_job, timeout=JOB_TIMEOUT_SECONDS)
        student_submissions = get_student_submissions(submissions_api, students)  # refresh submissions

    if any([s.workflow_state == "published" for s in student_submissions]):
        print("Some submissions are in 'published' state. Forcing unsubmission...")
        unsubmit_job = submissions_api.unsubmit_all([s.course_user.id for s in student_submissions])
        client.jobs.wait_for_completion(unsubmit_job, timeout=JOB_TIMEOUT_SECONDS)
        student_submissions = get_student_submissions(submissions_api, students)  # refresh submissions

    # verify all student submissions are in "attempting" state
    for submission in student_submissions:
        assert submission.workflow_state == "attempting", submission

    submission_jobs, report = submit_answers(
        submissions_api,
        user_files,
        fname_student_map,
        user_submission_map,
        config.file_question_map,
    )

    if config.report_path:
        with open(config.report_path, "w") as f:
            yaml.dump(report, f)
        print(f"Wrote submission report to {config.report_path}")

    return submission_jobs


@click.command()
@click.argument("config_path")
def main(config_path: Path) -> None:
    """CLI entry point.

    Args:
        config_path: Path to the YAML configuration file.
    """
    submission_jobs = run(config_path)
    print(f"Submitted {len(submission_jobs)} files for grading.")


if __name__ == "__main__":
    main()
