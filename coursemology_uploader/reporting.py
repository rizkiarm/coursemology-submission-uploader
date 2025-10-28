"""Report generation utilities for YAML and CSV formats."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from coursemology_uploader.types import SubmissionReport


def _save_report_as_yaml(report: dict[str, SubmissionReport], report_path: Path) -> None:
    """Save submission report to YAML file.

    Args:
        report: Submission report dictionary.
        report_path: Path to save the report.

    Raises:
        OSError: If report cannot be written.
    """
    with open(report_path, "w") as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False)
    print(f"Wrote submission report to {report_path} (YAML format)")


def _save_report_as_csv(report: dict[str, SubmissionReport], report_path: Path) -> None:
    """Save submission report to CSV file.

    Args:
        report: Submission report dictionary.
        report_path: Path to save the report.

    Raises:
        OSError: If report cannot be written.
    """
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(
            [
                "User Directory",
                "Student Name",
                "Student Email",
                "Student ID",
                "Submitted Files",
                "No Match Files",
                "No Submission Questions",
                "Errors",
            ]
        )

        # Write data rows
        for fname, data in sorted(report.items()):
            student = data["student"]
            writer.writerow(
                [
                    fname,
                    student["name"] if student else "",
                    student["email"] if student else "",
                    student["id"] if student else "",
                    ", ".join(sorted(data["submitted"])),
                    ", ".join(sorted(data["no_match"])),
                    ", ".join(sorted(data["no_submission"])),
                    "; ".join(sorted(data["errors"])),
                ]
            )

    print(f"Wrote submission report to {report_path} (CSV format)")


def save_report(report: dict[str, SubmissionReport], report_path: Path) -> None:
    """Save submission report to file (YAML or CSV based on extension).

    Args:
        report: Submission report dictionary.
        report_path: Path to save the report.

    Raises:
        OSError: If report cannot be written.
        ValueError: If file extension is not supported.
    """
    suffix = report_path.suffix.lower()

    if suffix in [".yaml", ".yml"]:
        _save_report_as_yaml(report, report_path)
    elif suffix == ".csv":
        _save_report_as_csv(report, report_path)
    else:
        raise ValueError(f"Unsupported report file extension: {suffix}. Supported formats: .yaml, .yml, .csv")
