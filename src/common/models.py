"""
Common Pydantic models shared across all GPS services
"""

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class Coordinate(BaseModel):
    """GPS coordinate with validation"""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees")
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitude in degrees"
    )

    @classmethod
    def from_tuple(cls, coord_tuple: Tuple[float, float]) -> "Coordinate":
        """Create coordinate from tuple [lat, lng]"""
        if len(coord_tuple) != 2:
            raise ValueError("Coordinate tuple must have exactly 2 elements")
        return cls(latitude=coord_tuple[0], longitude=coord_tuple[1])


class GPSPoint(BaseModel):
    """GPS point with comprehensive validation"""

    coordinate: Coordinate
    time_offset_seconds: Optional[float] = Field(
        None, ge=0, description="Seconds from activity start"
    )
    elevation_meters: Optional[float] = Field(
        None, ge=-1000, le=10000, description="Elevation in meters"
    )

    @field_validator("time_offset_seconds")
    @classmethod
    def validate_time_offset(cls, v):
        if v is not None and v > 86400 * 7:  # More than 7 days seems unreasonable
            raise ValueError("Time offset too large (max 7 days)")
        return v


class ExportConfig(BaseModel):
    """Configuration for export operations with validation"""

    count: int = Field(
        ..., gt=0, le=10000, description="Number of activities to export"
    )
    output_dir: str = Field(..., min_length=1, description="Output directory path")
    delay_seconds: float = Field(..., ge=0, le=60, description="Delay between requests")
    organize_by_type: bool = Field(
        default=False, description="Organize files by activity type"
    )
    resume: bool = Field(default=False, description="Resume from previous export")

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v):
        """Validate output directory path"""
        if not v or not v.strip():
            raise ValueError("Output directory cannot be empty")

        # Basic path validation
        try:
            from pathlib import Path

            Path(v)
            return v.strip()
        except (ValueError, OSError) as e:
            raise ValueError(f"Invalid path: {e}")


class ProgressData(BaseModel):
    """Progress tracking data with validation"""

    exported_activities: List[int] = Field(
        default_factory=list, description="List of exported activity IDs"
    )
    last_activity_index: int = Field(
        default=0, ge=0, description="Index of last processed activity"
    )

    @field_validator("exported_activities")
    @classmethod
    def validate_activity_ids(cls, v):
        """Ensure all activity IDs are positive integers"""
        if not isinstance(v, list):
            raise ValueError("exported_activities must be a list")
        for activity_id in v:
            if not isinstance(activity_id, int) or activity_id <= 0:
                raise ValueError(f"Invalid activity ID: {activity_id}")
        return v
