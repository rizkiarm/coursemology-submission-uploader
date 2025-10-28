from dataclasses import dataclass
from pathlib import Path
from re import Pattern

import yaml


@dataclass
class BasicAuthConfig:
    """Basic HTTP authentication credentials for protected directory indexes."""

    username: str
    password: str


@dataclass
class BatchDownloadConfig:
    """Configuration for scraping, filtering, and downloading files from a directory index.

    Attributes:
        base_url: Root URL of the directory index.
        basic_auth: Optional HTTP basic auth credentials.
        filter_pattern: Regex or string pattern to filter files to download.
        destination: Local directory to save downloaded files.
    """

    base_url: str
    basic_auth: BasicAuthConfig | None
    filter_pattern: str | Pattern[str]
    destination: Path


@dataclass
class NameUserMapConfig:
    """Configuration describing how to map filenames to student identities via CSV.

    Attributes:
        csv: Path to the CSV file.
        key: Column name used as the lookup key (e.g., filename or ID).
        name: Column name containing the student's full name.
        email: Column name containing the student's email.
    """

    csv: str
    key: str
    name: str
    email: str


@dataclass
class CoursemologyConfig:
    """Coursemology authentication and assessment selection.

    Attributes:
        username: Coursemology login username.
        password: Coursemology login password.
        course_id: Target course ID.
        assessment_category: Category title containing the assessment.
        assessment_title: Target assessment title.
    """

    username: str
    password: str
    course_id: int
    assessment_category: str
    assessment_title: str


@dataclass
class Config:
    """Top-level configuration for the uploader workflow.

    Attributes:
        base_dir: Base directory containing (extracted) student files.
        file_pattern: Glob pattern to locate student files.
        fname_user_map: CSV-based mapping configuration from filename key to user info.
        file_answer_map: Mapping of filename regex to answer index in Coursemology.
        coursemology: Coursemology credentials and assessment info.
        batch_download: Optional configuration to download and extract submissions.
    """

    base_dir: Path
    file_pattern: str
    fname_user_map: NameUserMapConfig
    file_question_map: dict[str, str]
    coursemology: CoursemologyConfig
    report_path: Path | None = None
    batch_download: BatchDownloadConfig | None = None


def load_config(path: Path) -> Config:
    """Load YAML configuration.

    Args:
        path: Path to YAML config.

    Returns:
        Parsed Config object.
    """
    with open(path) as f:
        yaml_config = yaml.safe_load(f)
    config = Config(
        base_dir=Path(yaml_config["base_dir"]),
        file_pattern=yaml_config["file_pattern"],
        report_path=yaml_config["report_path"] if "report_path" in yaml_config else None,
        fname_user_map=NameUserMapConfig(
            csv=yaml_config["fname_user_map"]["csv"],
            key=yaml_config["fname_user_map"]["key"],
            name=yaml_config["fname_user_map"]["name"],
            email=yaml_config["fname_user_map"]["email"],
        ),
        file_question_map=yaml_config["file_question_map"],
        coursemology=CoursemologyConfig(
            username=yaml_config["coursemology"]["username"],
            password=yaml_config["coursemology"]["password"],
            course_id=yaml_config["coursemology"]["course_id"],
            assessment_category=yaml_config["coursemology"]["assessment_category"],
            assessment_title=yaml_config["coursemology"]["assessment_title"],
        ),
        batch_download=BatchDownloadConfig(
            base_url=yaml_config["batch_download"]["base_url"],
            basic_auth=BasicAuthConfig(
                username=yaml_config["batch_download"]["basic_auth"]["username"],
                password=yaml_config["batch_download"]["basic_auth"]["password"],
            )
            if "basic_auth" in yaml_config["batch_download"]
            else None,
            filter_pattern=yaml_config["batch_download"]["filter_pattern"],
            destination=Path(yaml_config["batch_download"]["destination"]),
        )
        if "batch_download" in yaml_config
        else None,
    )
    return config
