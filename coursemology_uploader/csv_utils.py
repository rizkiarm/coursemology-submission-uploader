"""CSV utility functions for mapping data from CSV files."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def _validate_csv_file(csv_file: Path) -> None:
    """Validate that CSV file exists.

    Args:
        csv_file: Path to the CSV file.

    Raises:
        FileNotFoundError: If CSV file doesn't exist.
    """
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")


def _validate_columns(
    fieldnames: Sequence[str],
    key_column: str,
    value_columns: list[str] | None = None,
    value_column: str | None = None,
) -> None:
    """Validate that required columns exist in CSV headers.

    Args:
        fieldnames: Sequence of field names from CSV.
        key_column: Key column name to validate.
        value_columns: Optional list of value column names.
        value_column: Optional single value column name.

    Raises:
        KeyError: If required columns are not found.
    """
    if key_column not in fieldnames:
        raise KeyError(f"Key column '{key_column}' not found in CSV headers: {fieldnames}")

    if value_column and value_column not in fieldnames:
        raise KeyError(f"Value column '{value_column}' not found in CSV headers: {fieldnames}")

    if value_columns:
        missing_columns = [col for col in value_columns if col not in fieldnames]
        if missing_columns:
            raise KeyError(f"Value columns {missing_columns} not found in CSV headers: {fieldnames}")


def csv_to_map(
    csv_file: str | Path,
    key_column: str,
    value_column: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    skip_empty: bool = True,
) -> dict[str, str]:
    """Read a CSV file and convert it to a dictionary mapping.

    Args:
        csv_file: Path to the CSV file.
        key_column: Column name to use as dictionary keys.
        value_column: Column name to use as dictionary values.
        encoding: File encoding (default: 'utf-8').
        delimiter: CSV delimiter (default: ',').
        skip_empty: Whether to skip rows with empty key or value (default: True).

    Returns:
        Dictionary mapping key column values to value column values.

    Raises:
        FileNotFoundError: If CSV file doesn't exist.
        KeyError: If column names are not found in CSV headers.
    """
    csv_file_path = Path(csv_file)
    _validate_csv_file(csv_file_path)

    result_map: dict[str, str] = {}

    with open(csv_file_path, encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)

        assert reader.fieldnames is not None, "CSV file has no headers"
        _validate_columns(reader.fieldnames, key_column, value_column=value_column)

        # Process rows
        for row in reader:
            key = row[key_column]
            value = row[value_column]

            # Skip empty values if requested
            if skip_empty and (not key or not value):
                continue

            result_map[key] = value

    return result_map


def csv_to_map_multiple_values(
    csv_file: str | Path,
    key_column: str,
    value_columns: list[str],
    encoding: str = "utf-8",
    delimiter: str = ",",
    skip_empty: bool = True,
) -> dict[str, dict[str, str]]:
    """Read a CSV and create a map where each key maps to a dictionary of multiple values.

    Args:
        csv_file: Path to the CSV file.
        key_column: Column name to use as dictionary keys.
        value_columns: List of column names to include as values.
        encoding: File encoding (default: 'utf-8').
        delimiter: CSV delimiter (default: ',').
        skip_empty: Whether to skip rows with empty keys (default: True).

    Returns:
        Dictionary mapping keys to dictionaries of column values.

    Raises:
        FileNotFoundError: If CSV file doesn't exist.
        KeyError: If column names are not found in CSV headers.
    """
    csv_file_path = Path(csv_file)
    _validate_csv_file(csv_file_path)

    result_map: dict[str, dict[str, str]] = {}

    with open(csv_file_path, encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)

        assert reader.fieldnames is not None, "CSV file has no headers"
        _validate_columns(reader.fieldnames, key_column, value_columns=value_columns)

        # Process rows
        for row in reader:
            key = row[key_column]

            # Skip empty keys if requested
            if skip_empty and not key:
                continue

            # Build value dictionary
            value_dict = {col: row[col] for col in value_columns}
            result_map[key] = value_dict

    return result_map
