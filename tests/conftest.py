"""
Shared test configuration and fixtures for GPXBridge
"""

import pytest
import tempfile
from pathlib import Path
import arrow

# Disable loguru during tests to reduce noise
import loguru

loguru.logger.disable("src")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_coordinate_data():
    """Sample GPS coordinate data for testing"""
    return {
        "valid_coordinates": [
            (0.0, 0.0),
            (45.0, -122.0),
            (90.0, 180.0),
            (-90.0, -180.0),
            (47.6062, -122.3321),  # Seattle
        ],
        "invalid_coordinates": [
            (91.0, 0.0),  # Lat too high
            (-91.0, 0.0),  # Lat too low
            (0.0, 181.0),  # Lng too high
            (0.0, -181.0),  # Lng too low
            (float("inf"), 0.0),  # Invalid float
            (0.0, float("nan")),  # NaN
        ],
        "invalid_types": [
            ("not_a_number", 0.0),
            (0.0, "not_a_number"),
            (None, 0.0),
            (0.0, None),
            ([], []),
        ],
    }


@pytest.fixture
def sample_nested_dict():
    """Sample nested dictionary for testing safe_get_nested"""
    return {
        "level1": {
            "level2": {"level3": "deep_value", "list_item": [1, 2, 3], "empty": None},
            "simple": "value",
        },
        "empty_dict": {},
        "none_value": None,
    }


@pytest.fixture
def sample_date_strings():
    """Sample date strings for testing date parsing"""
    return {
        "valid_iso": "2024-01-15T10:30:00Z",
        "valid_local": "2024-01-15T10:30:00",
        "valid_date_only": "2024-01-15",
        "valid_with_tz": "2024-01-15T10:30:00-08:00",
        "invalid_format": "not-a-date",
        "invalid_values": "2024-13-40T25:70:70Z",
        "empty": "",
        "none": None,
        "partial": "2024-01",
    }


@pytest.fixture
def sample_text_for_slugify():
    """Sample text data for testing slugification"""
    return {
        "simple": "Hello World",
        "with_spaces": "  Multiple   Spaces  ",
        "with_special": "Hello, World! & More #stuff",
        "unicode": "Café & Résumé",
        "long_text": "A" * 100,  # Test max_length
        "empty": "",
        "whitespace_only": "   ",
        "numbers": "123 456 789",
        "mixed": "Test-Case_with.periods",
        "emoji": "Hello 👋 World 🌍",
        "none": None,
        "non_string": 12345,
    }


@pytest.fixture
def sample_strava_activity():
    """Sample Strava activity data for testing"""
    return {
        "id": 12345,
        "name": "Morning Run",
        "type": "Run",
        "start_date_local": "2024-01-15T07:30:00",
        "distance_meters": 5000.0,
        "moving_time_seconds": 1800,
        "total_elevation_gain_meters": 100.0,
    }


@pytest.fixture
def invalid_strava_activity_data():
    """Invalid Strava activity data for validation testing"""
    return [
        # Invalid ID
        {
            "id": -1,
            "name": "Test",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        },
        {
            "id": 0,
            "name": "Test",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        },
        # Invalid name
        {"id": 1, "name": "", "type": "Run", "start_date_local": "2024-01-15T07:30:00"},
        {
            "id": 1,
            "name": "   ",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        },
        {
            "id": 1,
            "name": "A" * 201,
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        },
        # Invalid type
        {
            "id": 1,
            "name": "Test",
            "type": "",
            "start_date_local": "2024-01-15T07:30:00",
        },
        {
            "id": 1,
            "name": "Test",
            "type": "A" * 51,
            "start_date_local": "2024-01-15T07:30:00",
        },
        # Invalid date
        {"id": 1, "name": "Test", "type": "Run", "start_date_local": "invalid-date"},
        # Invalid numeric fields
        {
            "id": 1,
            "name": "Test",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
            "distance_meters": -1,
        },
        {
            "id": 1,
            "name": "Test",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
            "moving_time_seconds": -1,
        },
    ]


@pytest.fixture
def sample_export_config():
    """Sample export configuration for testing"""
    return {
        "count": 10,
        "output_dir": "./test_exports",
        "delay_seconds": 1.0,
        "organize_by_type": False,
        "resume": False,
    }


@pytest.fixture
def current_time():
    """Fixed current time for testing"""
    return arrow.get("2024-01-15T12:00:00Z")


@pytest.fixture
def mock_cwd(tmp_path):
    """Mock current working directory"""
    return tmp_path
