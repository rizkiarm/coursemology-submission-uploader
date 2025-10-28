"""High-level workflow orchestration for submission uploading."""

from __future__ import annotations

import time
from pathlib import Path

from coursemology_py.api.course.submissions import AssessmentSubmissionsAPI
from coursemology_py.client import CoursemologyClient
from coursemology_py.models.common import JobSubmitted
from coursemology_py.models.course.submissions import AssessmentSubmission
from coursemology_py.models.course.users import CourseUser
from tqdm import tqdm

from coursemology_uploader.configs import BatchDownloadConfig, load_config
from coursemology_uploader.coursemology_queries import (
    get_assessment,
    get_category,
    get_student_submissions,
)
from coursemology_uploader.downloader import download_files
from coursemology_uploader.extractor import extract_zip_files
from coursemology_uploader.file_mapping import (
    get_fname_student_map,
    get_user_files,
    load_fname_user_map,
)
from coursemology_uploader.reporting import save_report
from coursemology_uploader.scraper import filter_urls, scrape_directory_index
from coursemology_uploader.submission_handler import submit_answers


def perform_batch_download(config: BatchDownloadConfig) -> list[Path]:
    """Scrape a directory index, filter URLs, and download matching files.

    Args:
        config: Batch download configuration.

    Returns:
        List of downloaded file paths.

    Raises:
        ValueError: If download fails.
    """
    basic_auth_username = config.basic_auth.username if config.basic_auth else None
    basic_auth_password = config.basic_auth.password if config.basic_auth else None

    urls = scrape_directory_index(config.base_url, basic_auth_username, basic_auth_password)
    filtered_urls = filter_urls(urls, pattern=config.filter_pattern)

    return download_files(
        filtered_urls,
        config.destination,
        username=basic_auth_username,
        password=basic_auth_password,
    )


def _wait_for_auto_grading(
    submissions_api: AssessmentSubmissionsAPI,
    student_submissions: list[AssessmentSubmission],
    students: list[CourseUser],
    grading_max_wait_seconds: int,
    grading_poll_interval_seconds: int,
) -> list[AssessmentSubmission]:
    """Wait for auto-grading to complete for submissions in 'submitted' state.

    Args:
        submissions_api: Assessment submissions API.
        student_submissions: Current list of submissions.
        students: List of students.
        grading_max_wait_seconds: Maximum time to wait for grading.
        grading_poll_interval_seconds: Interval between status checks.

    Returns:
        Updated list of submissions after grading completes or timeout.
    """
    submitted_count = sum(1 for s in student_submissions if s.workflow_state == "submitted")
    if submitted_count == 0:
        return student_submissions

    initial_submitted = submitted_count
    max_iterations = grading_max_wait_seconds // grading_poll_interval_seconds

    with tqdm(
        total=initial_submitted,
        desc="Waiting for auto-grading",
        unit="submission",
    ) as pbar:
        for _ in range(max_iterations):
            student_submissions = get_student_submissions(submissions_api, students)
            new_submitted_count = sum(1 for s in student_submissions if s.workflow_state == "submitted")

            # Update progress bar based on graded submissions
            graded_this_iteration = submitted_count - new_submitted_count
            if graded_this_iteration > 0:
                pbar.update(graded_this_iteration)
                submitted_count = new_submitted_count

            if submitted_count == 0:
                pbar.set_description("All submissions graded")
                break

            pbar.set_description(f"{submitted_count} remaining")
            time.sleep(grading_poll_interval_seconds)

    # Check if any are still in submitted state after timeout
    remaining_submitted = [s for s in student_submissions if s.workflow_state == "submitted"]
    if remaining_submitted:
        raise TimeoutError(
            f"Auto-grading did not complete within {grading_max_wait_seconds}s. "
            f"{len(remaining_submitted)} submission(s) still in 'submitted' state."
        )

    return student_submissions


def _ensure_submissions_in_attempting_state(
    submissions_api: AssessmentSubmissionsAPI,
    student_submissions: list[AssessmentSubmission],
    students: list[CourseUser],
    client: CoursemologyClient,
    job_timeout_seconds: int,
    grading_max_wait_seconds: int,
    grading_poll_interval_seconds: int,
) -> list[AssessmentSubmission]:
    """Ensure all submissions are in 'attempting' state.

    Handles force submit for unstarted and unsubmit for published submissions.

    Args:
        submissions_api: Assessment submissions API.
        student_submissions: Current list of submissions.
        students: List of students.
        client: Coursemology client for job waiting.
        job_timeout_seconds: Timeout for background jobs.
        grading_max_wait_seconds: Maximum time to wait for grading.
        grading_poll_interval_seconds: Interval between status checks.

    Returns:
        Updated list of submissions in 'attempting' state.

    Raises:
        AssertionError: If any submission is not in 'attempting' state after operations.
    """
    student_ids = [s.course_user.id for s in student_submissions]

    # Force submit any unstarted submissions
    unstarted_count = sum(1 for s in student_submissions if s.workflow_state == "unstarted")
    if unstarted_count > 0:
        print(f"Force submitting {unstarted_count} unstarted submission(s)...")
        submit_job = submissions_api.force_submit_all(student_ids)
        client.jobs.wait_for_completion(submit_job, timeout=job_timeout_seconds)
        student_submissions = get_student_submissions(submissions_api, students)

    # Wait for auto-grading to complete
    student_submissions = _wait_for_auto_grading(
        submissions_api,
        student_submissions,
        students,
        grading_max_wait_seconds,
        grading_poll_interval_seconds,
    )

    # Unsubmit any published submissions
    published_count = sum(1 for s in student_submissions if s.workflow_state == "published")
    if published_count > 0:
        print(f"Unsubmitting {published_count} published submission(s)...")
        unsubmit_job = submissions_api.unsubmit_all(student_ids)
        client.jobs.wait_for_completion(unsubmit_job, timeout=job_timeout_seconds)
        student_submissions = get_student_submissions(submissions_api, students)

    # Verify all submissions are in attempting state
    for submission in student_submissions:
        assert submission.workflow_state == "attempting", (
            f"Submission {submission.id} for user {submission.course_user.id} "
            f"is in state '{submission.workflow_state}', expected 'attempting'"
        )

    return student_submissions


def _handle_batch_download(config: BatchDownloadConfig, expected_base_dir: Path) -> None:
    """Handle batch download and extraction if configured.

    Args:
        config: Batch download configuration.
        expected_base_dir: Expected base directory for extracted files.

    Raises:
        AssertionError: If extracted path doesn't match expected base directory.
    """
    print("Downloading files...")
    downloaded_paths = perform_batch_download(config)

    print("Extracting archives...")
    extracted_path = extract_zip_files(downloaded_paths, expected_base_dir)

    assert expected_base_dir == extracted_path, (
        f"Base directory mismatch: expected {expected_base_dir}, got {extracted_path}"
    )


def run(config_path: Path) -> list[JobSubmitted]:
    """Main workflow function.

    Reads configuration, optionally downloads/extracts submissions, resolves
    students and submissions, and uploads programming answers.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        List of JobSubmitted for all uploaded files.

    Raises:
        FileNotFoundError: If config or required files don't exist.
        ValueError: If assessment/category/students cannot be found.
    """
    # Load configuration
    config = load_config(config_path)

    # Optional: Download and extract submissions
    if config.batch_download:
        _handle_batch_download(config.batch_download, config.base_dir)

    # Load user files
    user_files = get_user_files(config.base_dir, config.file_pattern)
    print(f"Loaded {len(user_files)} user(s) with files matching '{config.file_pattern}'")

    # Authenticate with Coursemology
    client = CoursemologyClient()
    client.login(config.coursemology.username, config.coursemology.password)
    course_api = client.course(config.coursemology.course_id)
    print(f"Logged in as {config.coursemology.username}")

    # Load and map students
    students = course_api.users.index_students().users
    fname_user_map = load_fname_user_map(config.fname_user_map)
    fname_student_map = get_fname_student_map(config.fname_user_map, students, fname_user_map)
    print(f"Mapped {len(fname_student_map)}/{len(fname_user_map)} students to files")

    # Find assessment
    assessment_api = course_api.assessment
    category = get_category(assessment_api, config.coursemology.assessment_category)
    assessment = get_assessment(assessment_api, category.id, config.coursemology.assessment_title)
    print(f"Target: {category.title} / {assessment.title}")

    # Get and prepare submissions
    submissions_api = assessment_api.submissions(assessment.id)
    student_submissions = get_student_submissions(submissions_api, students)
    user_submission_map = {s.course_user.id: s for s in student_submissions}

    student_submissions = _ensure_submissions_in_attempting_state(
        submissions_api,
        student_submissions,
        students,
        client,
        config.operational.job_timeout_seconds,
        config.operational.grading_max_wait_seconds,
        config.operational.grading_poll_interval_seconds,
    )

    # Submit answers
    submission_jobs, report = submit_answers(
        submissions_api,
        user_files,
        fname_student_map,
        user_submission_map,
        config.file_question_map,
        config.operational.no_submission_content,
    )

    # Save report if configured
    if config.report_path:
        save_report(report, config.report_path)
        print(f"Report saved to: {config.report_path}")

    print(f"✓ Completed {len(submission_jobs)} submission(s)")
    return submission_jobs
