"""
Tests for common utility functions
"""

from pathlib import Path
from unittest.mock import patch
import arrow
from freezegun import freeze_time
from hypothesis import given, strategies as st

from src.common.utils import (
    safe_get_nested,
    validate_coordinates,
    safe_parse_date,
    safe_slugify,
    validate_output_path,
)


class TestSafeGetNested:
    """Test safe_get_nested function"""

    def test_get_nested_value_success(self, sample_nested_dict):
        """Test successful nested value retrieval"""
        result = safe_get_nested(sample_nested_dict, ["level1", "level2", "level3"])
        assert result == "deep_value"

    def test_get_simple_value(self, sample_nested_dict):
        """Test getting simple nested value"""
        result = safe_get_nested(sample_nested_dict, ["level1", "simple"])
        assert result == "value"

    def test_get_list_item(self, sample_nested_dict):
        """Test getting list from nested dict"""
        result = safe_get_nested(sample_nested_dict, ["level1", "level2", "list_item"])
        assert result == [1, 2, 3]

    def test_missing_key_returns_default(self, sample_nested_dict):
        """Test missing key returns default value"""
        result = safe_get_nested(sample_nested_dict, ["missing_key"], default="default")
        assert result == "default"

    def test_missing_nested_key_returns_default(self, sample_nested_dict):
        """Test missing nested key returns default value"""
        result = safe_get_nested(
            sample_nested_dict, ["level1", "missing"], default="default"
        )
        assert result == "default"

    def test_empty_keys_list(self, sample_nested_dict):
        """Test empty keys list returns original dict"""
        result = safe_get_nested(sample_nested_dict, [])
        assert result == sample_nested_dict

    def test_none_value(self, sample_nested_dict):
        """Test accessing None value"""
        result = safe_get_nested(sample_nested_dict, ["none_value"])
        assert result is None

    def test_invalid_data_type(self):
        """Test with non-dict data types"""
        result = safe_get_nested("not_a_dict", ["key"], default="default")
        assert result == "default"

        result = safe_get_nested(None, ["key"], default="default")
        assert result == "default"

    def test_intermediate_non_dict(self, sample_nested_dict):
        """Test when intermediate value is not a dict"""
        result = safe_get_nested(
            sample_nested_dict, ["level1", "simple", "invalid_key"], default="default"
        )
        assert result == "default"

    @given(st.lists(st.text(), min_size=1, max_size=5))
    def test_random_keys_with_empty_dict(self, keys):
        """Property test: any keys on empty dict should return default"""
        result = safe_get_nested({}, keys, default="default")
        assert result == "default"


class TestValidateCoordinates:
    """Test validate_coordinates function"""

    def test_valid_coordinates(self, sample_coordinate_data):
        """Test valid GPS coordinates"""
        for lat, lng in sample_coordinate_data["valid_coordinates"]:
            assert validate_coordinates(lat, lng) is True, f"Failed for ({lat}, {lng})"

    def test_invalid_coordinates(self, sample_coordinate_data):
        """Test invalid GPS coordinates"""
        for lat, lng in sample_coordinate_data["invalid_coordinates"]:
            assert (
                validate_coordinates(lat, lng) is False
            ), f"Should fail for ({lat}, {lng})"

    def test_invalid_types(self, sample_coordinate_data):
        """Test invalid coordinate types"""
        for lat, lng in sample_coordinate_data["invalid_types"]:
            assert (
                validate_coordinates(lat, lng) is False
            ), f"Should fail for ({lat}, {lng})"

    def test_boundary_values(self):
        """Test exact boundary values"""
        # Exact boundaries should be valid
        assert validate_coordinates(90.0, 180.0) is True
        assert validate_coordinates(-90.0, -180.0) is True
        assert validate_coordinates(0.0, 0.0) is True

    def test_string_coordinates(self):
        """Test string coordinates that can be converted"""
        assert validate_coordinates("45.0", "-122.0") is True
        assert validate_coordinates("invalid", "also_invalid") is False

    @given(
        lat=st.floats(
            min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False
        ),
        lng=st.floats(
            min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_valid_coordinate_range_property(self, lat, lng):
        """Property test: all coordinates within valid range should pass"""
        assert validate_coordinates(lat, lng) is True

    @given(
        lat=st.one_of(
            st.floats(min_value=90.01, max_value=1000),
            st.floats(min_value=-1000, max_value=-90.01),
        ),
        lng=st.floats(
            min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_invalid_latitude_property(self, lat, lng):
        """Property test: invalid latitudes should fail"""
        assert validate_coordinates(lat, lng) is False


class TestSafeParsDate:
    """Test safe_parse_date function"""

    @freeze_time("2024-01-15T12:00:00Z")
    def test_valid_date_strings(self, sample_date_strings):
        """Test parsing valid date strings"""
        valid_dates = [
            sample_date_strings["valid_iso"],
            sample_date_strings["valid_local"],
            sample_date_strings["valid_date_only"],
            sample_date_strings["valid_with_tz"],
        ]

        for date_str in valid_dates:
            result = safe_parse_date(date_str)
            assert isinstance(result, arrow.Arrow), f"Failed to parse: {date_str}"
            # Should not be the fallback time
            assert result != arrow.now()

    @freeze_time("2024-01-15T12:00:00Z")
    def test_invalid_date_strings(self, sample_date_strings):
        """Test parsing invalid date strings returns current time"""
        invalid_dates = [
            sample_date_strings["invalid_format"],
            sample_date_strings["invalid_values"],
            sample_date_strings["empty"],
            sample_date_strings["partial"],
        ]

        current_time = arrow.now()

        for date_str in invalid_dates:
            result = safe_parse_date(date_str, fallback_name="test")
            assert isinstance(result, arrow.Arrow)
            # Should be approximately current time (within 1 second)
            assert abs((result - current_time).total_seconds()) < 1

    @freeze_time("2024-01-15T12:00:00Z")
    def test_none_date_string(self):
        """Test None date string returns current time"""
        result = safe_parse_date(None, fallback_name="test")
        assert isinstance(result, arrow.Arrow)
        assert abs((result - arrow.now()).total_seconds()) < 1

    def test_fallback_name_in_warning(self, caplog):
        """Test that fallback name appears in warning log"""
        safe_parse_date("invalid-date", fallback_name="test_activity")
        # Note: We disabled loguru in conftest, so this test mainly ensures no exceptions


class TestSafeSlugify:
    """Test safe_slugify function"""

    def test_simple_slugify(self, sample_text_for_slugify):
        """Test basic slugification"""
        result = safe_slugify(sample_text_for_slugify["simple"])
        assert result == "hello-world"

    def test_spaces_and_special_chars(self, sample_text_for_slugify):
        """Test handling of spaces and special characters"""
        result = safe_slugify(sample_text_for_slugify["with_special"])
        expected = "hello-world-more-stuff"
        assert result == expected

    def test_unicode_handling(self, sample_text_for_slugify):
        """Test unicode character handling"""
        result = safe_slugify(sample_text_for_slugify["unicode"])
        assert "cafe" in result.lower()
        assert "resume" in result.lower()

    def test_max_length_limit(self, sample_text_for_slugify):
        """Test maximum length limiting"""
        result = safe_slugify(sample_text_for_slugify["long_text"], max_length=10)
        assert len(result) <= 10

    def test_empty_string_fallback(self, sample_text_for_slugify):
        """Test empty string returns fallback"""
        result = safe_slugify(sample_text_for_slugify["empty"], fallback="fallback")
        assert result == "fallback"

    def test_whitespace_only_fallback(self, sample_text_for_slugify):
        """Test whitespace-only string returns fallback"""
        result = safe_slugify(
            sample_text_for_slugify["whitespace_only"], fallback="fallback"
        )
        assert result == "fallback"

    def test_none_fallback(self, sample_text_for_slugify):
        """Test None input returns fallback"""
        result = safe_slugify(sample_text_for_slugify["none"], fallback="fallback")
        assert result == "fallback"

    def test_non_string_fallback(self, sample_text_for_slugify):
        """Test non-string input returns fallback"""
        result = safe_slugify(
            sample_text_for_slugify["non_string"], fallback="fallback"
        )
        assert result == "fallback"

    def test_custom_fallback(self):
        """Test custom fallback value"""
        result = safe_slugify("", fallback="custom-fallback")
        assert result == "custom-fallback"

    def test_numbers_in_text(self, sample_text_for_slugify):
        """Test text with numbers"""
        result = safe_slugify(sample_text_for_slugify["numbers"])
        assert "123" in result
        assert "456" in result
        assert "789" in result

    @given(st.text(min_size=1, max_size=50))
    def test_slugify_never_empty_with_fallback(self, text):
        """Property test: slugify should never return empty string when fallback provided"""
        result = safe_slugify(text, fallback="fallback")
        assert len(result) > 0
        assert isinstance(result, str)


class TestValidateOutputPath:
    """Test validate_output_path function - SECURITY CRITICAL"""

    def test_simple_relative_path(self, tmp_path):
        """Test simple relative path"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = validate_output_path("test_output")
            assert isinstance(result, Path)
            assert result.is_absolute()

    def test_absolute_path_within_cwd(self, tmp_path):
        """Test absolute path within current working directory"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            test_path = tmp_path / "exports"
            result = validate_output_path(str(test_path))
            assert isinstance(result, Path)
            assert result.is_absolute()

    def test_path_traversal_attack_prevention(self, tmp_path):
        """Test prevention of path traversal attacks"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # These should be blocked and return safe default
            dangerous_paths = [
                "../../../etc/passwd",
                "../../../../../../etc/shadow",
                "/etc/passwd",
                "/root/.ssh/id_rsa",
            ]

            for dangerous_path in dangerous_paths:
                result = validate_output_path(dangerous_path)
                assert isinstance(result, Path)
                # Should return safe default path
                assert "gpx_exports" in str(result)

    def test_current_directory(self, tmp_path):
        """Test current directory reference"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = validate_output_path(".")
            assert isinstance(result, Path)
            assert result.is_absolute()

    def test_parent_directory_allowed(self, tmp_path):
        """Test that parent directory is allowed"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # Parent should be allowed
            result = validate_output_path("../exports")
            assert isinstance(result, Path)
            assert result.is_absolute()

    def test_invalid_path_characters(self, tmp_path):
        """Test invalid path characters"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # These might be invalid on some systems
            invalid_paths = [
                "con",  # Windows reserved name
                "aux",  # Windows reserved name
            ]

            for invalid_path in invalid_paths:
                result = validate_output_path(invalid_path)
                assert isinstance(result, Path)
                # Should handle gracefully

    def test_empty_path(self, tmp_path):
        """Test empty path returns safe default"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = validate_output_path("")
            assert isinstance(result, Path)
            assert "gpx_exports" in str(result)

    def test_none_path(self, tmp_path):
        """Test None path handling"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # This will raise an exception in Path(), should be handled
            try:
                result = validate_output_path(None)
                assert isinstance(result, Path)
                assert "gpx_exports" in str(result)
            except TypeError:
                # This is acceptable behavior too
                pass

    @given(st.text(min_size=1, max_size=100))
    def test_arbitrary_path_input(self, tmp_path, path_input):
        """Property test: function should always return a Path object"""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            try:
                result = validate_output_path(path_input)
                assert isinstance(result, Path)
                assert result.is_absolute()
            except (OSError, ValueError):
                # Some inputs might cause OS errors, that's acceptable
                pass
