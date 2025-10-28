"""Web scraping utilities for directory indexes."""

import re
from collections import deque
from re import Pattern
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth


def scrape_directory_index(
    url: str, username: str | None = None, password: str | None = None, timeout: int = 30, recursive: bool = True
) -> list[str]:
    """
    Scrape a directory index page to get list of files and directories.

    Args:
        url: URL of the directory index page
        username: Optional basic auth username
        password: Optional basic auth password
        timeout: Request timeout in seconds
        recursive: Whether to recursively scan subdirectories

    Returns:
        List of URLs to files and directories

    Raises:
        requests.RequestException: For HTTP/network errors
        ValueError: For parsing errors
    """
    if not url:
        raise ValueError("URL is required")

    # Ensure URL ends with /
    if not url.endswith("/"):
        url += "/"

    auth = HTTPBasicAuth(username, password) if username and password else None

    # Initialize queue with the starting URL and tracking sets
    queue: deque[str] = deque([url])
    visited: set[str] = set()
    all_links: list[str] = []

    while queue:
        current_url = queue.popleft()

        # Skip if already visited
        if current_url in visited:
            continue

        visited.add(current_url)

        try:
            response = requests.get(current_url, auth=auth, timeout=timeout)
            response.raise_for_status()

            # Check if we got HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                print(f"Warning: {current_url} is not HTML - skipping")
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            # Find all links on current page
            page_links: list[str] = []
            for a_tag in soup.find_all("a", href=True):
                # BeautifulSoup attributes can be lists or other types; ensure we only handle strings
                href_attr = a_tag.get("href")
                if not isinstance(href_attr, str):
                    continue

                # Skip parent directory links and anchors
                if href_attr in ["../", "../", "/"] or href_attr.startswith("#") or href_attr.startswith("?"):
                    continue

                # Convert relative URLs to absolute
                full_url: str = urljoin(current_url, href_attr)

                # Only include links that are within the same domain and path
                if _is_valid_subdirectory(url, full_url):
                    page_links.append(full_url)

            print(f"Found {len(page_links)} links in {current_url}")

            # Add all links to results
            all_links.extend(page_links)

            # If recursive, add directories to queue for further processing
            if recursive:
                for sub_url in page_links:
                    if sub_url.endswith("/") and sub_url not in visited:
                        queue.append(sub_url)

        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to fetch {current_url}: {e}")
            continue
        except Exception as e:
            print(f"Warning: Error processing {current_url}: {e}")
            continue

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_links: list[str] = []
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def _is_valid_subdirectory(base_url: str, target_url: str) -> bool:
    """
    Check if target_url is a valid subdirectory or file within base_url.

    Args:
        base_url: The original base URL
        target_url: The URL to check

    Returns:
        True if target_url is within the base_url scope
    """
    base_parsed = urlparse(base_url)
    target_parsed = urlparse(target_url)

    # Must be same scheme and netloc (domain)
    if base_parsed.scheme != target_parsed.scheme or base_parsed.netloc != target_parsed.netloc:
        return False

    # Target path must start with base path
    base_path = base_parsed.path.rstrip("/")
    target_path = target_parsed.path.rstrip("/")

    # Allow exact match or subdirectory
    return target_path.startswith(base_path)


def filter_urls(urls: list[str], pattern: str | Pattern[str], use_regex: bool = True) -> list[str]:
    """
    Filter a list of URLs based on a keyword or regex pattern.

    Args:
        urls: List of URLs to filter
        pattern: String pattern or compiled regex pattern
        use_regex: Whether to treat pattern as regex (default: True)

    Returns:
        Filtered list of URLs

    Raises:
        re.error: If regex pattern is invalid
    """
    if not urls:
        return []

    if use_regex:
        if isinstance(pattern, str):
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
        else:
            compiled_pattern = pattern

        return [url for url in urls if compiled_pattern.search(url)]
    else:
        # Simple string matching
        pattern_str = str(pattern).lower()
        return [url for url in urls if pattern_str in url.lower()]
