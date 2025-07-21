"""
Strava-specific Pydantic models
"""

from typing import Optional
import arrow
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientSettings(BaseSettings):
    """Strava API configuration using environment variables"""

    model_config = SettingsConfigDict(env_prefix="STRAVA_")

    client_id: str = Field(..., description="Strava API client ID", min_length=1)
    client_secret: str = Field(
        ...,
        description="Strava API client secret",
        min_length=1,
    )
    refresh_token: str = Field(
        ...,
        description="Strava refresh token",
        min_length=1,
    )


class StravaActivity(BaseModel):
    """Strava activity model with explicit units and validation"""

    id: int = Field(..., gt=0, description="Strava activity ID")
    name: str = Field(..., min_length=1, max_length=200, description="Activity name")
    type: str = Field(..., min_length=1, max_length=50, description="Activity type")
    start_date_local: str = Field(..., description="Activity start date in local time")
    distance_meters: Optional[float] = Field(
        None, ge=0, description="Distance in meters"
    )
    moving_time_seconds: Optional[int] = Field(
        None, ge=0, description="Moving time in seconds"
    )
    total_elevation_gain_meters: Optional[float] = Field(
        None, ge=0, description="Elevation gain in meters"
    )

    @field_validator("start_date_local")
    @classmethod
    def validate_date_format(cls, v):
        """Validate date string can be parsed by Arrow"""
        if not v or not v.strip():
            raise ValueError("Invalid date format: empty date")

        try:
            # Arrow can be too permissive, so check basic format requirements
            if len(v.strip()) < 10:  # Minimum for YYYY-MM-DD
                raise ValueError("Invalid date format: too short")

            arrow.get(v)
            return v
        except (arrow.ParserError, ValueError) as e:
            raise ValueError(f"Invalid date format: {e}")

    @field_validator("name", "type")
    @classmethod
    def validate_string_fields(cls, v):
        """Ensure string fields are properly cleaned"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()


class RateLimitInfo(BaseModel):
    """Rate limit tracking model with validation"""

    model_config = {"populate_by_name": True}

    fifteen_min_usage: int = Field(default=0, ge=0, alias="15min_usage")
    fifteen_min_limit: int = Field(default=100, gt=0, alias="15min_limit")
    daily_usage: int = Field(default=0, ge=0)
    daily_limit: int = Field(default=1000, gt=0)

    @model_validator(mode="after")
    def validate_limits(self):
        """Ensure usage doesn't exceed limits"""
        if self.fifteen_min_usage > self.fifteen_min_limit:
            self.fifteen_min_usage = self.fifteen_min_limit
        if self.daily_usage > self.daily_limit:
            self.daily_usage = self.daily_limit
        return self
