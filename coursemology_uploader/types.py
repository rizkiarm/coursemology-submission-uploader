"""Type definitions for coursemology uploader."""

from __future__ import annotations

from typing import TypedDict


class StudentInfo(TypedDict):
    """Type definition for student information in reports."""

    name: str
    email: str
    id: str


class SubmissionReport(TypedDict):
    """Type definition for submission report entries."""

    student: StudentInfo | None
    errors: list[str]
    submitted: list[str]
    no_match: list[str]
    no_submission: list[str]
