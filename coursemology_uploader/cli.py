"""Command-line interface for coursemology submission uploader."""

from __future__ import annotations

from pathlib import Path

import click

from coursemology_uploader.workflow import run


@click.command()
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
def main(config_path: Path) -> None:
    """CLI entry point for coursemology submission uploader.

    Args:
        config_path: Path to the YAML configuration file.
    """
    try:
        submission_jobs = run(config_path)
        print(f"Successfully submitted {len(submission_jobs)} files for grading.")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
