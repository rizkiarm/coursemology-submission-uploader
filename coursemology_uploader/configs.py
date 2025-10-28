"""Configuration models for coursemology submission uploader."""

from __future__ import annotations

from pathlib import Path
from re import Pattern
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

# Default operational settings
DEFAULT_JOB_TIMEOUT_SECONDS: int = 3600  # 1 hour - Wait time for Coursemology background jobs
DEFAULT_NO_SUBMISSION_CONTENT: str = "# No submission"
DEFAULT_GRADING_MAX_WAIT_SECONDS: int = 3600  # 1 hour - Wait for auto-grading
DEFAULT_GRADING_POLL_INTERVAL_SECONDS: int = 5  # Check every 5 seconds


class BasicAuthConfig(BaseModel):
    """Basic HTTP authentication credentials for protected directory indexes."""

    username: str
    password: str


class BatchDownloadConfig(BaseModel):
    """Configuration for scraping, filtering, and downloading files from a directory index.

    Attributes:
        base_url: Root URL of the directory index.
        basic_auth: Optional HTTP basic auth credentials.
        filter_pattern: Regex or string pattern to filter files to download.
        destination: Local directory to save downloaded files.
    """

    base_url: str
    basic_auth: BasicAuthConfig | None = None
    filter_pattern: str | Pattern[str]
    destination: Path

    @field_validator("destination", mode="before")
    @classmethod
    def convert_destination_to_path(cls, v: Any) -> Path:
        """Convert destination to Path object."""
        return Path(v) if not isinstance(v, Path) else v


class NameUserMapConfig(BaseModel):
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


class CoursemologyConfig(BaseModel):
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


class OperationalConfig(BaseModel):
    """Operational settings for timeouts and default content.

    Attributes:
        job_timeout_seconds: Timeout for Coursemology background jobs.
        no_submission_content: Default content for questions with no submission.
        grading_max_wait_seconds: Maximum time to wait for auto-grading.
        grading_poll_interval_seconds: Interval between grading status checks.
    """

    job_timeout_seconds: int = DEFAULT_JOB_TIMEOUT_SECONDS
    no_submission_content: str = DEFAULT_NO_SUBMISSION_CONTENT
    grading_max_wait_seconds: int = DEFAULT_GRADING_MAX_WAIT_SECONDS
    grading_poll_interval_seconds: int = DEFAULT_GRADING_POLL_INTERVAL_SECONDS


class Config(BaseModel):
    """Top-level configuration for the uploader workflow.

    Attributes:
        base_dir: Base directory containing (extracted) student files.
        file_pattern: Glob pattern to locate student files.
        fname_user_map: CSV-based mapping configuration from filename key to user info.
        file_question_map: Mapping of filename regex to question title in Coursemology.
        coursemology: Coursemology credentials and assessment info.
        report_path: Optional path to save submission report.
        batch_download: Optional configuration to download and extract submissions.
        operational: Operational settings for timeouts and defaults.
    """

    base_dir: Path
    file_pattern: str
    fname_user_map: NameUserMapConfig
    file_question_map: dict[str, str] = Field(default_factory=dict)
    coursemology: CoursemologyConfig
    report_path: Path | None = None
    batch_download: BatchDownloadConfig | None = None
    operational: OperationalConfig = Field(default_factory=OperationalConfig)

    @field_validator("base_dir", mode="before")
    @classmethod
    def convert_base_dir_to_path(cls, v: Any) -> Path:
        """Convert base_dir to Path object."""
        return Path(v) if not isinstance(v, Path) else v

    @field_validator("report_path", mode="before")
    @classmethod
    def convert_report_path_to_path(cls, v: Any) -> Path | None:
        """Convert report_path to Path object."""
        if v is None:
            return None
        return Path(v) if not isinstance(v, Path) else v


def load_config(path: Path) -> Config:
    """Load YAML configuration and parse into Config model.

    Args:
        path: Path to YAML config.

    Returns:
        Parsed Config object with full validation.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If YAML is malformed.
        pydantic.ValidationError: If config structure is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        yaml_data = yaml.safe_load(f)

    # Use Pydantic's validation
    return Config.model_validate(yaml_data)
