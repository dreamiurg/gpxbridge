"""Tests for common Pydantic models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from hypothesis import given, strategies as st

from src.common.models import (
    Coordinate,
    GPSPoint,
    ExportConfig,
    ProgressData,
)


class TestCoordinate:
    """Test Coordinate model validation"""

    def test_valid_coordinate_creation(self, sample_coordinate_data):
        """Test creating valid coordinates"""
        for lat, lng in sample_coordinate_data["valid_coordinates"]:
            coord = Coordinate(latitude=lat, longitude=lng)
            assert coord.latitude == lat
            assert coord.longitude == lng

    def test_invalid_latitude_bounds(self):
        """Test latitude boundary validation"""
        with pytest.raises(ValidationError) as exc_info:
            Coordinate(latitude=91.0, longitude=0.0)
        assert "Input should be less than or equal to 90" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            Coordinate(latitude=-91.0, longitude=0.0)
        assert "Input should be greater than or equal to -90" in str(exc_info.value)

    def test_invalid_longitude_bounds(self):
        """Test longitude boundary validation"""
        with pytest.raises(ValidationError) as exc_info:
            Coordinate(latitude=0.0, longitude=181.0)
        assert "Input should be less than or equal to 180" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            Coordinate(latitude=0.0, longitude=-181.0)
        assert "Input should be greater than or equal to -180" in str(exc_info.value)

    def test_from_tuple_valid(self, sample_coordinate_data):
        """Test creating coordinate from valid tuple"""
        for lat, lng in sample_coordinate_data["valid_coordinates"]:
            coord = Coordinate.from_tuple((lat, lng))
            assert coord.latitude == lat
            assert coord.longitude == lng

    def test_from_tuple_invalid_length(self):
        """Test tuple with wrong number of elements"""
        with pytest.raises(ValueError) as exc_info:
            Coordinate.from_tuple((45.0,))  # Only one element
        assert "exactly 2 elements" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            Coordinate.from_tuple((45.0, -122.0, 100.0))  # Three elements
        assert "exactly 2 elements" in str(exc_info.value)

    def test_from_tuple_invalid_coordinates(self):
        """Test tuple with invalid coordinate values"""
        with pytest.raises(ValidationError):
            Coordinate.from_tuple((91.0, 0.0))  # Invalid latitude

    def test_coordinate_serialization(self):
        """Test coordinate serialization"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)
        data = coord.model_dump()
        assert data == {"latitude": 45.0, "longitude": -122.0}

    @given(
        lat=st.floats(
            min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False
        ),
        lng=st.floats(
            min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_coordinate_property_test(self, lat, lng):
        """Property test: valid ranges should always work"""
        coord = Coordinate(latitude=lat, longitude=lng)
        assert coord.latitude == lat
        assert coord.longitude == lng


class TestGPSPoint:
    """Test GPSPoint model validation"""

    def test_valid_gps_point_creation(self):
        """Test creating valid GPS point"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)
        point = GPSPoint(
            coordinate=coord, time_offset_seconds=120.0, elevation_meters=500.0
        )
        assert point.coordinate == coord
        assert point.time_offset_seconds == 120.0
        assert point.elevation_meters == 500.0

    def test_gps_point_minimal(self):
        """Test GPS point with only coordinate"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)
        point = GPSPoint(coordinate=coord)
        assert point.coordinate == coord
        assert point.time_offset_seconds is None
        assert point.elevation_meters is None

    def test_invalid_time_offset(self):
        """Test invalid time offset validation"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)

        # Negative time offset
        with pytest.raises(ValidationError) as exc_info:
            GPSPoint(coordinate=coord, time_offset_seconds=-1.0)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_time_offset_too_large(self):
        """Test time offset that's too large (> 7 days)"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)

        # More than 7 days in seconds
        too_large = 86400 * 8  # 8 days
        with pytest.raises(ValidationError) as exc_info:
            GPSPoint(coordinate=coord, time_offset_seconds=too_large)
        assert "Time offset too large" in str(exc_info.value)

    def test_valid_time_offset_boundary(self):
        """Test time offset at 7-day boundary"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)

        # Exactly 7 days should be valid
        exactly_7_days = 86400 * 7
        point = GPSPoint(coordinate=coord, time_offset_seconds=exactly_7_days)
        assert point.time_offset_seconds == exactly_7_days

    def test_invalid_elevation_bounds(self):
        """Test elevation boundary validation"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)

        # Too low elevation
        with pytest.raises(ValidationError) as exc_info:
            GPSPoint(coordinate=coord, elevation_meters=-1001.0)
        assert "Input should be greater than or equal to -1000" in str(exc_info.value)

        # Too high elevation
        with pytest.raises(ValidationError) as exc_info:
            GPSPoint(coordinate=coord, elevation_meters=10001.0)
        assert "Input should be less than or equal to 10000" in str(exc_info.value)

    def test_elevation_boundary_values(self):
        """Test elevation at boundary values"""
        coord = Coordinate(latitude=45.0, longitude=-122.0)

        # Minimum elevation
        point_min = GPSPoint(coordinate=coord, elevation_meters=-1000.0)
        assert point_min.elevation_meters == -1000.0

        # Maximum elevation
        point_max = GPSPoint(coordinate=coord, elevation_meters=10000.0)
        assert point_max.elevation_meters == 10000.0


class TestExportConfig:
    """Test ExportConfig model validation"""

    def test_valid_export_config(self, sample_export_config):
        """Test creating valid export configuration"""
        config = ExportConfig(**sample_export_config)
        assert config.count == sample_export_config["count"]
        assert config.output_dir == sample_export_config["output_dir"]
        assert config.delay_seconds == sample_export_config["delay_seconds"]
        assert config.organize_by_type == sample_export_config["organize_by_type"]
        assert config.resume == sample_export_config["resume"]
        assert config.activity_type is None
        assert config.after is None
        assert config.before is None

    def test_invalid_count_bounds(self):
        """Test count boundary validation"""
        base_config = {"count": 10, "output_dir": "./test", "delay_seconds": 1.0}

        # Count too low
        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**{**base_config, "count": 0})
        assert "Input should be greater than 0" in str(exc_info.value)

        # Count too high
        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**{**base_config, "count": 10001})
        assert "Input should be less than or equal to 10000" in str(exc_info.value)

    def test_invalid_delay_bounds(self):
        """Test delay_seconds boundary validation"""
        base_config = {"count": 10, "output_dir": "./test", "delay_seconds": 1.0}

        # Negative delay
        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**{**base_config, "delay_seconds": -1.0})
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

        # Delay too high
        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**{**base_config, "delay_seconds": 61.0})
        assert "Input should be less than or equal to 60" in str(exc_info.value)

    def test_empty_output_dir(self):
        """Test empty output directory validation"""
        base_config = {"count": 10, "output_dir": "", "delay_seconds": 1.0}

        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**base_config)
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_whitespace_only_output_dir(self):
        """Test whitespace-only output directory"""
        base_config = {"count": 10, "output_dir": "   ", "delay_seconds": 1.0}

        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(**base_config)
        assert "Output directory cannot be empty" in str(exc_info.value)

    def test_output_dir_trimmed(self):
        """Test output directory is trimmed"""
        config = ExportConfig(count=10, output_dir="  ./test_dir  ", delay_seconds=1.0)
        assert config.output_dir == "./test_dir"

    def test_default_values(self):
        """Test default values are applied"""
        config = ExportConfig(count=10, output_dir="./test", delay_seconds=1.0)
        assert config.organize_by_type is False
        assert config.resume is False

    def test_boolean_field_validation(self):
        """Test boolean fields accept various inputs"""
        config = ExportConfig(
            count=10,
            output_dir="./test",
            delay_seconds=1.0,
            organize_by_type=True,
            resume=True,
        )
        assert config.organize_by_type is True
        assert config.resume is True

    def test_datetime_bounds_validation(self):
        """Ensure date filters are normalized and validated"""

        after = datetime(2024, 1, 1, 8, tzinfo=timezone.utc)
        before = datetime(2024, 2, 1, 8, tzinfo=timezone.utc)
        config = ExportConfig(
            count=5,
            output_dir="./test",
            delay_seconds=1.0,
            activity_type="Run",
            after=after,
            before=before,
        )
        assert config.after == after
        assert config.before == before
        assert config.activity_type == "Run"

        with pytest.raises(ValidationError) as exc_info:
            ExportConfig(
                count=5,
                output_dir="./test",
                delay_seconds=1.0,
                after=before,
                before=after,
            )

        assert "'after' must be earlier than 'before'" in str(exc_info.value)

    def test_progress_signature_changes_with_filters(self):
        """The progress signature should change with filter inputs"""

        base = ExportConfig(count=5, output_dir="./test", delay_seconds=1.0)
        filtered = ExportConfig(
            count=5,
            output_dir="./test",
            delay_seconds=1.0,
            activity_type="Run",
        )
        assert base.progress_signature() != filtered.progress_signature()


class TestProgressData:
    """Test ProgressData model validation"""

    def test_valid_progress_data(self):
        """Test creating valid progress data"""
        progress = ProgressData(
            exported_activities=[1, 2, 3, 4, 5],
            last_activity_index=4,
            config_signature="abc123",
        )
        assert progress.exported_activities == [1, 2, 3, 4, 5]
        assert progress.last_activity_index == 4
        assert progress.config_signature == "abc123"

    def test_default_values(self):
        """Test default values are applied"""
        progress = ProgressData()
        assert progress.exported_activities == []
        assert progress.last_activity_index == 0
        assert progress.config_signature is None

    def test_invalid_activity_ids(self):
        """Test invalid activity IDs validation"""
        # Zero activity ID
        with pytest.raises(ValidationError) as exc_info:
            ProgressData(exported_activities=[1, 2, 0, 4])
        assert "Invalid activity ID: 0" in str(exc_info.value)

        # Negative activity ID
        with pytest.raises(ValidationError) as exc_info:
            ProgressData(exported_activities=[1, 2, -1, 4])
        assert "Invalid activity ID: -1" in str(exc_info.value)

    def test_non_integer_activity_ids(self):
        """Test non-integer activity IDs"""
        with pytest.raises(ValidationError) as exc_info:
            ProgressData(exported_activities=[1, 2, "invalid", 4])
        assert "unable to parse string" in str(exc_info.value)

    def test_invalid_signature(self):
        """Progress signature cannot be empty"""

        with pytest.raises(ValidationError) as exc_info:
            ProgressData(config_signature="   ")

        assert "config_signature cannot be empty" in str(exc_info.value)

    def test_invalid_activity_list_type(self):
        """Test non-list activity IDs"""
        with pytest.raises(ValidationError) as exc_info:
            ProgressData(exported_activities="not_a_list")
        assert "Input should be a valid list" in str(exc_info.value)

    def test_negative_last_activity_index(self):
        """Test negative last activity index"""
        with pytest.raises(ValidationError) as exc_info:
            ProgressData(last_activity_index=-1)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_large_activity_list(self):
        """Test with large activity list"""
        large_list = list(range(1, 1001))  # 1000 activity IDs
        progress = ProgressData(exported_activities=large_list)
        assert len(progress.exported_activities) == 1000
        assert progress.exported_activities[0] == 1
        assert progress.exported_activities[-1] == 1000

    @given(
        st.lists(st.integers(min_value=1, max_value=999999), min_size=0, max_size=100)
    )
    def test_valid_activity_ids_property(self, activity_ids):
        """Property test: positive integers should always be valid activity IDs"""
        progress = ProgressData(exported_activities=activity_ids)
        assert progress.exported_activities == activity_ids

    def test_progress_data_serialization(self):
        """Test progress data serialization"""
        progress = ProgressData(exported_activities=[1, 2, 3], last_activity_index=2)
        data = progress.model_dump()
        expected = {
            "exported_activities": [1, 2, 3],
            "last_activity_index": 2,
            "config_signature": None,
        }
        assert data == expected
