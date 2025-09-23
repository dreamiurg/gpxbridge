"""
Common utility functions shared across all GPS services
"""

import arrow
from pathlib import Path
from loguru import logger
from slugify import slugify


def safe_get_nested(data: dict, keys: list, default=None):
    """Safely get nested dictionary values"""
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default


def validate_coordinates(lat: float, lng: float) -> bool:
    """Validate latitude and longitude are within valid ranges"""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
        return -90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0
    except (ValueError, TypeError):
        return False


def safe_parse_date(date_str: str, fallback_name: str = "Unknown") -> arrow.Arrow:
    """Safely parse date string with fallback"""
    try:
        return arrow.get(date_str)
    except (arrow.ParserError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse date '{date_str}' for {fallback_name}: {e}")
        return arrow.now()


def safe_slugify(text: str, max_length: int = 30, fallback: str = "unknown") -> str:
    """Safely slugify text with fallback for empty results"""
    if not text or not isinstance(text, str):
        return fallback

    result = slugify(text, max_length=max_length)
    return result if result else fallback


def validate_output_path(output_dir: str) -> Path:
    """Validate and resolve output directory path to prevent traversal"""
    try:
        # Resolve the path and ensure it's absolute
        path = Path(output_dir).resolve()

        # Ensure it's not trying to escape the current working directory
        cwd = Path.cwd().resolve()

        # Check if the path is within or adjacent to CWD (allow relative paths)
        try:
            path.relative_to(cwd.parent)
        except ValueError:
            # Path is outside allowed area, use safe default
            logger.warning(
                f"Output path '{output_dir}' outside safe area, using './exports'"
            )
            return Path("./exports").resolve()

        return path
    except (OSError, ValueError) as e:
        logger.warning(f"Invalid output path '{output_dir}': {e}, using './exports'")
        return Path("./exports").resolve()
