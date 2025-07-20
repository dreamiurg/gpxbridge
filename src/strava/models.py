"""
Strava-specific Pydantic models
"""

from typing import Optional
import arrow
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class ClientSettings(BaseSettings):
    """Strava API configuration using environment variables"""

    client_id: str = Field(
        ..., env="STRAVA_CLIENT_ID", description="Strava API client ID", min_length=1
    )
    client_secret: str = Field(
        ...,
        env="STRAVA_CLIENT_SECRET",
        description="Strava API client secret",
        min_length=1,
    )
    refresh_token: str = Field(
        ...,
        env="STRAVA_REFRESH_TOKEN",
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
        try:
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

    fifteen_min_usage: int = Field(default=0, ge=0, alias="15min_usage")
    fifteen_min_limit: int = Field(default=100, gt=0, alias="15min_limit")
    daily_usage: int = Field(default=0, ge=0, alias="daily_usage")
    daily_limit: int = Field(default=1000, gt=0, alias="daily_limit")

    @model_validator(mode="before")
    @classmethod
    def validate_limits(cls, values):
        """Ensure usage doesn't exceed limits"""
        if isinstance(values, dict):
            if values.get("fifteen_min_usage", 0) > values.get(
                "fifteen_min_limit", 100
            ):
                values["fifteen_min_usage"] = values.get("fifteen_min_limit", 100)
            if values.get("daily_usage", 0) > values.get("daily_limit", 1000):
                values["daily_usage"] = values.get("daily_limit", 1000)
        return values
