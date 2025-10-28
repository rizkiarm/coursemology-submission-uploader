"""File and user mapping utilities."""

from __future__ import annotations

from pathlib import Path

from coursemology_py.models.course.users import CourseUser

from coursemology_uploader.configs import NameUserMapConfig
from coursemology_uploader.csv_utils import csv_to_map_multiple_values


def load_fname_user_map(config: NameUserMapConfig) -> dict[str, dict[str, str]]:
    """Load filename-to-user mapping from a CSV.

    Args:
        config: CSV mapping configuration.

    Returns:
        Mapping from CSV key to a dict containing user name and email.

    Raises:
        FileNotFoundError: If CSV file doesn't exist.
        KeyError: If required columns are missing.
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

    Raises:
        ValueError: If base_dir doesn't exist or is not a directory.
    """
    if not base_dir.exists():
        raise ValueError(f"Base directory does not exist: {base_dir}")
    if not base_dir.is_dir():
        raise ValueError(f"Base directory is not a directory: {base_dir}")

    user_files: dict[str, dict[str, Path]] = {}

    for filepath in base_dir.glob(pattern):
        user_dir_name = filepath.parent.name
        if user_dir_name not in user_files:
            user_files[user_dir_name] = {}
        user_files[user_dir_name][filepath.name] = filepath

    return user_files


def _match_student_by_email_or_name(
    user_data: dict[str, str],
    email_key: str,
    name_key: str,
    email_student_map: dict[str, CourseUser],
    name_student_map: dict[str, CourseUser],
) -> CourseUser | None:
    """Helper function to match a student by email or name.

    Args:
        user_data: Dictionary containing user email and name.
        email_key: Key for email in user_data.
        name_key: Key for name in user_data.
        email_student_map: Mapping of email to CourseUser.
        name_student_map: Mapping of name to CourseUser.

    Returns:
        Matched CourseUser or None if no match found.
    """
    email = user_data.get(email_key, "")
    name = user_data.get(name_key, "")

    if email in email_student_map:
        return email_student_map[email]
    if name in name_student_map:
        return name_student_map[name]

    return None


def get_fname_student_map(
    config: NameUserMapConfig,
    students: list[CourseUser],
    fname_user_map: dict[str, dict[str, str]],
) -> dict[str, CourseUser]:
    """Resolve filename keys to CourseUser records by email or name.

    Args:
        config: Mapping config indicating which CSV columns correspond to name/email.
        students: List of CourseUser objects from Coursemology.
        fname_user_map: Mapping from filename key to name/email data.

    Returns:
        Mapping from filename key to CourseUser. Unmatched entries are logged.
    """
    email_student_map = {s.email: s for s in students}
    name_student_map = {s.name: s for s in students}
    fname_student_map: dict[str, CourseUser] = {}

    for fname, user_data in fname_user_map.items():
        matched_student = _match_student_by_email_or_name(
            user_data,
            config.email,
            config.name,
            email_student_map,
            name_student_map,
        )

        if matched_student:
            fname_student_map[fname] = matched_student
        else:
            email = user_data.get(config.email, "")
            name = user_data.get(config.name, "")
            print(f"Could not find student for fname {fname} with name {name} and email {email}")

    return fname_student_map
