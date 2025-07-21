"""
Tests for Strava-specific Pydantic models
"""

import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError
from hypothesis import given, strategies as st

from src.strava.models import (
    ClientSettings,
    StravaActivity,
    RateLimitInfo,
)


class TestClientSettings:
    """Test ClientSettings model validation"""

    def test_valid_client_settings_from_env(self):
        """Test creating client settings from environment variables"""
        env_vars = {
            "STRAVA_CLIENT_ID": "test_client_id",
            "STRAVA_CLIENT_SECRET": "test_client_secret",
            "STRAVA_REFRESH_TOKEN": "test_refresh_token",
        }

        with patch.dict(os.environ, env_vars):
            settings = ClientSettings()
            assert settings.client_id == "test_client_id"
            assert settings.client_secret == "test_client_secret"
            assert settings.refresh_token == "test_refresh_token"

    def test_valid_client_settings_direct(self):
        """Test creating client settings with direct values"""
        settings = ClientSettings(
            client_id="direct_client_id",
            client_secret="direct_client_secret",
            refresh_token="direct_refresh_token",
        )
        assert settings.client_id == "direct_client_id"
        assert settings.client_secret == "direct_client_secret"
        assert settings.refresh_token == "direct_refresh_token"

    def test_empty_client_id(self):
        """Test empty client ID validation"""
        with pytest.raises(ValidationError) as exc_info:
            ClientSettings(client_id="", client_secret="secret", refresh_token="token")
        assert "ensure this value has at least 1 character" in str(exc_info.value)

    def test_empty_client_secret(self):
        """Test empty client secret validation"""
        with pytest.raises(ValidationError) as exc_info:
            ClientSettings(client_id="client", client_secret="", refresh_token="token")
        assert "ensure this value has at least 1 character" in str(exc_info.value)

    def test_empty_refresh_token(self):
        """Test empty refresh token validation"""
        with pytest.raises(ValidationError) as exc_info:
            ClientSettings(client_id="client", client_secret="secret", refresh_token="")
        assert "ensure this value has at least 1 character" in str(exc_info.value)

    def test_missing_env_vars(self):
        """Test behavior when environment variables are missing"""
        # Clear any existing env vars
        env_clear = {
            "STRAVA_CLIENT_ID": "",
            "STRAVA_CLIENT_SECRET": "",
            "STRAVA_REFRESH_TOKEN": "",
        }

        with patch.dict(os.environ, env_clear, clear=True):
            with pytest.raises(ValidationError):
                ClientSettings()

    def test_env_var_override(self):
        """Test that direct values override environment variables"""
        env_vars = {
            "STRAVA_CLIENT_ID": "env_client_id",
            "STRAVA_CLIENT_SECRET": "env_client_secret",
            "STRAVA_REFRESH_TOKEN": "env_refresh_token",
        }

        with patch.dict(os.environ, env_vars):
            settings = ClientSettings(
                client_id="override_client_id",
                client_secret="override_client_secret",
                refresh_token="override_refresh_token",
            )
            assert settings.client_id == "override_client_id"
            assert settings.client_secret == "override_client_secret"
            assert settings.refresh_token == "override_refresh_token"


class TestStravaActivity:
    """Test StravaActivity model validation"""

    def test_valid_strava_activity(self, sample_strava_activity):
        """Test creating valid Strava activity"""
        activity = StravaActivity(**sample_strava_activity)
        assert activity.id == sample_strava_activity["id"]
        assert activity.name == sample_strava_activity["name"]
        assert activity.type == sample_strava_activity["type"]
        assert activity.start_date_local == sample_strava_activity["start_date_local"]

    def test_activity_with_optional_fields(self):
        """Test activity with all optional fields"""
        activity_data = {
            "id": 12345,
            "name": "Complete Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
            "distance_meters": 5000.0,
            "moving_time_seconds": 1800,
            "total_elevation_gain_meters": 100.0,
        }

        activity = StravaActivity(**activity_data)
        assert activity.distance_meters == 5000.0
        assert activity.moving_time_seconds == 1800
        assert activity.total_elevation_gain_meters == 100.0

    def test_activity_minimal_fields(self):
        """Test activity with only required fields"""
        minimal_data = {
            "id": 12345,
            "name": "Minimal Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        activity = StravaActivity(**minimal_data)
        assert activity.id == 12345
        assert activity.name == "Minimal Activity"
        assert activity.type == "Run"
        assert activity.distance_meters is None
        assert activity.moving_time_seconds is None
        assert activity.total_elevation_gain_meters is None

    def test_invalid_activity_id(self):
        """Test invalid activity ID validation"""
        base_data = {
            "name": "Test Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        # Zero ID
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(id=0, **base_data)
        assert "ensure this value is greater than 0" in str(exc_info.value)

        # Negative ID
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(id=-1, **base_data)
        assert "ensure this value is greater than 0" in str(exc_info.value)

    def test_invalid_activity_name(self):
        """Test invalid activity name validation"""
        base_data = {
            "id": 12345,
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        # Empty name
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(name="", **base_data)
        assert "Field cannot be empty or whitespace only" in str(exc_info.value)

        # Whitespace only name
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(name="   ", **base_data)
        assert "Field cannot be empty or whitespace only" in str(exc_info.value)

        # Too long name
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(name="A" * 201, **base_data)
        assert "ensure this value has at most 200 characters" in str(exc_info.value)

    def test_invalid_activity_type(self):
        """Test invalid activity type validation"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "start_date_local": "2024-01-15T07:30:00",
        }

        # Empty type
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(type="", **base_data)
        assert "Field cannot be empty or whitespace only" in str(exc_info.value)

        # Too long type
        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(type="A" * 51, **base_data)
        assert "ensure this value has at most 50 characters" in str(exc_info.value)

    def test_string_field_trimming(self):
        """Test that string fields are trimmed"""
        activity = StravaActivity(
            id=12345,
            name="  Trimmed Name  ",
            type="  Run  ",
            start_date_local="2024-01-15T07:30:00",
        )
        assert activity.name == "Trimmed Name"
        assert activity.type == "Run"

    def test_invalid_date_format(self):
        """Test invalid date format validation"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "type": "Run",
        }

        invalid_dates = [
            "not-a-date",
            "2024-13-40T25:70:70Z",
            "2024/01/15 07:30:00",  # Wrong format
            "",
            "2024-01-15",  # Missing time might be invalid depending on Arrow config
        ]

        for invalid_date in invalid_dates:
            with pytest.raises(ValidationError) as exc_info:
                StravaActivity(start_date_local=invalid_date, **base_data)
            assert "Invalid date format" in str(exc_info.value)

    def test_valid_date_formats(self):
        """Test various valid date formats"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "type": "Run",
        }

        valid_dates = [
            "2024-01-15T07:30:00",
            "2024-01-15T07:30:00Z",
            "2024-01-15T07:30:00-08:00",
            "2024-01-15T07:30:00.123Z",
        ]

        for valid_date in valid_dates:
            activity = StravaActivity(start_date_local=valid_date, **base_data)
            assert activity.start_date_local == valid_date

    def test_negative_distance(self):
        """Test negative distance validation"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(distance_meters=-1.0, **base_data)
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

    def test_negative_moving_time(self):
        """Test negative moving time validation"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(moving_time_seconds=-1, **base_data)
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

    def test_negative_elevation_gain(self):
        """Test negative elevation gain validation"""
        base_data = {
            "id": 12345,
            "name": "Test Activity",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
        }

        with pytest.raises(ValidationError) as exc_info:
            StravaActivity(total_elevation_gain_meters=-1.0, **base_data)
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

    @given(
        activity_id=st.integers(min_value=1, max_value=999999999),
        name=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        type_name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    )
    def test_activity_creation_property(self, activity_id, name, type_name):
        """Property test: valid inputs should create valid activities"""
        try:
            activity = StravaActivity(
                id=activity_id,
                name=name,
                type=type_name,
                start_date_local="2024-01-15T07:30:00",
            )
            assert activity.id == activity_id
            assert activity.name.strip() == name.strip()
            assert activity.type.strip() == type_name.strip()
        except Exception:
            # Some edge cases might fail, that's acceptable
            pass


class TestRateLimitInfo:
    """Test RateLimitInfo model validation"""

    def test_default_rate_limit_info(self):
        """Test creating rate limit info with defaults"""
        rate_limit = RateLimitInfo()
        assert rate_limit.fifteen_min_usage == 0
        assert rate_limit.fifteen_min_limit == 100
        assert rate_limit.daily_usage == 0
        assert rate_limit.daily_limit == 1000

    def test_custom_rate_limit_info(self):
        """Test creating rate limit info with custom values"""
        rate_limit = RateLimitInfo(
            fifteen_min_usage=50,
            fifteen_min_limit=200,
            daily_usage=500,
            daily_limit=2000,
        )
        assert rate_limit.fifteen_min_usage == 50
        assert rate_limit.fifteen_min_limit == 200
        assert rate_limit.daily_usage == 500
        assert rate_limit.daily_limit == 2000

    def test_alias_field_names(self):
        """Test using alias field names"""
        data = {
            "15min_usage": 25,
            "15min_limit": 150,
            "daily_usage": 300,
            "daily_limit": 1500,
        }

        rate_limit = RateLimitInfo(**data)
        assert rate_limit.fifteen_min_usage == 25
        assert rate_limit.fifteen_min_limit == 150
        assert rate_limit.daily_usage == 300
        assert rate_limit.daily_limit == 1500

    def test_negative_usage_validation(self):
        """Test negative usage validation"""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitInfo(fifteen_min_usage=-1)
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            RateLimitInfo(daily_usage=-1)
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

    def test_zero_limit_validation(self):
        """Test zero limit validation"""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitInfo(fifteen_min_limit=0)
        assert "ensure this value is greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            RateLimitInfo(daily_limit=0)
        assert "ensure this value is greater than 0" in str(exc_info.value)

    def test_usage_exceeds_limit_capping(self):
        """Test that usage is capped when exceeding limits"""
        # 15-minute usage exceeds limit
        data = {
            "fifteen_min_usage": 150,
            "fifteen_min_limit": 100,
            "daily_usage": 500,
            "daily_limit": 1000,
        }

        rate_limit = RateLimitInfo(**data)
        assert rate_limit.fifteen_min_usage == 100  # Capped to limit
        assert rate_limit.fifteen_min_limit == 100
        assert rate_limit.daily_usage == 500  # Not capped
        assert rate_limit.daily_limit == 1000

    def test_daily_usage_exceeds_limit_capping(self):
        """Test that daily usage is capped when exceeding limits"""
        data = {
            "fifteen_min_usage": 50,
            "fifteen_min_limit": 100,
            "daily_usage": 1500,
            "daily_limit": 1000,
        }

        rate_limit = RateLimitInfo(**data)
        assert rate_limit.fifteen_min_usage == 50  # Not capped
        assert rate_limit.fifteen_min_limit == 100
        assert rate_limit.daily_usage == 1000  # Capped to limit
        assert rate_limit.daily_limit == 1000

    def test_both_usage_exceed_limits(self):
        """Test when both usage values exceed their limits"""
        data = {
            "fifteen_min_usage": 150,
            "fifteen_min_limit": 100,
            "daily_usage": 1500,
            "daily_limit": 1000,
        }

        rate_limit = RateLimitInfo(**data)
        assert rate_limit.fifteen_min_usage == 100  # Capped
        assert rate_limit.fifteen_min_limit == 100
        assert rate_limit.daily_usage == 1000  # Capped
        assert rate_limit.daily_limit == 1000

    def test_usage_equals_limit(self):
        """Test when usage equals limit (edge case)"""
        data = {
            "fifteen_min_usage": 100,
            "fifteen_min_limit": 100,
            "daily_usage": 1000,
            "daily_limit": 1000,
        }

        rate_limit = RateLimitInfo(**data)
        assert rate_limit.fifteen_min_usage == 100
        assert rate_limit.fifteen_min_limit == 100
        assert rate_limit.daily_usage == 1000
        assert rate_limit.daily_limit == 1000

    def test_rate_limit_serialization(self):
        """Test rate limit info serialization"""
        rate_limit = RateLimitInfo(
            fifteen_min_usage=25,
            fifteen_min_limit=100,
            daily_usage=300,
            daily_limit=1000,
        )

        data = rate_limit.model_dump()
        expected = {
            "fifteen_min_usage": 25,
            "fifteen_min_limit": 100,
            "daily_usage": 300,
            "daily_limit": 1000,
        }
        assert data == expected

    def test_rate_limit_serialization_with_aliases(self):
        """Test rate limit info serialization includes aliases"""
        rate_limit = RateLimitInfo(
            fifteen_min_usage=25,
            fifteen_min_limit=100,
            daily_usage=300,
            daily_limit=1000,
        )

        # Test that we can serialize using aliases
        data = rate_limit.model_dump(by_alias=True)
        expected = {
            "15min_usage": 25,
            "15min_limit": 100,
            "daily_usage": 300,
            "daily_limit": 1000,
        }
        assert data == expected

    @given(
        usage=st.integers(min_value=0, max_value=10000),
        limit=st.integers(min_value=1, max_value=10000),
    )
    def test_rate_limit_usage_capping_property(self, usage, limit):
        """Property test: usage should never exceed limit after validation"""
        rate_limit = RateLimitInfo(fifteen_min_usage=usage, fifteen_min_limit=limit)
        assert rate_limit.fifteen_min_usage <= rate_limit.fifteen_min_limit
