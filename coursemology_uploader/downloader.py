"""File download utilities."""

from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth


def download_file(
    url: str,
    output_path: Path | None = None,
    username: str | None = None,
    password: str | None = None,
    timeout: int = 30,
) -> Path:
    """
    Download a single file from URL.

    Args:
        url: URL to download
        output_path: Path to save file (if None, uses filename from URL)
        username: Optional basic auth username
        password: Optional basic auth password
        timeout: Request timeout in seconds

    Returns:
        Path to downloaded file

    Raises:
        requests.RequestException: For HTTP/network errors
        ValueError: For invalid responses
        OSError: For file system errors
    """
    if not url:
        raise ValueError("URL is required")

    auth = HTTPBasicAuth(username, password) if username and password else None

    # Determine output path
    if output_path is None:
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name
        if not filename:
            filename = "download"
        output_path = Path.cwd() / filename

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Download file
    response = requests.get(url, auth=auth, timeout=timeout, stream=True)
    response.raise_for_status()

    # Check if we got HTML (error page)
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type.lower():
        raise ValueError("Received HTML response - check credentials or URL")

    # Write file
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return output_path


def download_files(
    urls: list[str],
    output_dir: Path | None = None,
    username: str | None = None,
    password: str | None = None,
    timeout: int = 30,
) -> list[Path]:
    """
    Download multiple files from URLs.

    Args:
        urls: List of URLs to download
        output_dir: Directory to save files (default: current directory)
        username: Optional basic auth username
        password: Optional basic auth password
        timeout: Request timeout in seconds

    Returns:
        List of paths to successfully downloaded files

    Raises:
        ValueError: If no URLs provided
    """
    if not urls:
        raise ValueError("No URLs provided")

    if output_dir is None:
        output_dir = Path.cwd()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: list[Path] = []

    for url in urls:
        try:
            # Get filename from URL
            parsed_url = urlparse(url)
            filename = Path(parsed_url.path).name
            if not filename:
                filename = f"download_{len(downloaded_files)}"

            output_path = output_dir / filename

            # Handle duplicate filenames
            counter = 1
            original_path = output_path
            while output_path.exists():
                stem = original_path.stem
                suffix = original_path.suffix
                output_path = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            # Download using single file function
            downloaded_path = download_file(url, output_path, username, password, timeout)
            downloaded_files.append(downloaded_path)
            print(f"Downloaded: {downloaded_path}")

        except Exception as e:
            print(f"Failed to download {url}: {e}")
            continue

    return downloaded_files
