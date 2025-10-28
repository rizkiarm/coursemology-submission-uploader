"""ZIP file extraction utilities."""

import zipfile
from pathlib import Path


def extract_zip_file(zip_path: Path, extract_dir: Path | None = None) -> Path:
    """
    Extract a single ZIP file.

    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to (if None, creates subdir named after zip)

    Returns:
        Path to extraction directory

    Raises:
        zipfile.BadZipFile: If ZIP file is corrupted
        OSError: For file system errors
        ValueError: If file doesn't exist or isn't a ZIP
    """
    zip_path = Path(zip_path)

    if not zip_path.exists():
        raise ValueError(f"ZIP file not found: {zip_path}")

    if not zip_path.suffix.lower() == ".zip":
        raise ValueError(f"Not a ZIP file: {zip_path}")

    if extract_dir is None:
        extract_dir = zip_path.parent / zip_path.stem

    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    return extract_dir


def extract_zip_files(
    zip_paths: list[Path],
    extract_base_dir: Path | None = None,
    with_stem: bool = False,
) -> Path:
    """
    Extract multiple ZIP files into subdirectories.

    Args:
        zip_paths: List of paths to ZIP files
        extract_base_dir: Base directory for extractions (default: 'extracted' in current dir)

    Returns:
        Path to the base extraction directory

    Raises:
        ValueError: If no ZIP files provided
    """
    if not zip_paths:
        raise ValueError("No ZIP files provided")

    if extract_base_dir is None:
        extract_base_dir = Path.cwd() / "extracted"

    extract_base_dir = Path(extract_base_dir)
    extract_base_dir.mkdir(parents=True, exist_ok=True)

    for zip_path in zip_paths:
        try:
            zip_path = Path(zip_path)
            extract_subdir = extract_base_dir
            if with_stem:
                extract_subdir = extract_base_dir / zip_path.stem
            extract_zip_file(zip_path, extract_subdir)
            print(f"Extracted {zip_path} to {extract_subdir}")

        except Exception as e:
            print(f"Error extracting {zip_path}: {e}")
            continue

    return extract_base_dir
