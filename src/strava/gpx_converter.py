"""
Strava-specific GPX conversion functionality
"""

from typing import Dict, Optional
import gpxpy
import gpxpy.gpx
from loguru import logger

from ..common.utils import safe_get_nested, validate_coordinates, safe_parse_date
from ..common.gpx import GPXUtils


class StravaGPXConverter:
    """Converts Strava activity streams to GPX format"""

    @staticmethod
    def create_gpx_from_strava_streams(
        activity: Dict, streams: Dict
    ) -> Optional[gpxpy.gpx.GPX]:
        """Convert Strava activity streams to GPX format

        Args:
            activity: Strava activity data dict
            streams: Strava streams data dict with latlng, time, altitude

        Returns:
            GPX object or None if no valid GPS data
        """
        # Validate required Strava stream data
        latlng_data = safe_get_nested(streams, ["latlng", "data"])
        if not latlng_data:
            activity_id = activity.get("id", "unknown")
            logger.warning(f"No GPS data available for Strava activity {activity_id}")
            return None

        # Get activity metadata
        activity_id = activity.get("id", "unknown")
        activity_name = activity.get("name", f"Activity {activity_id}")

        # Create GPX with metadata
        gpx = GPXUtils.create_empty_gpx(
            name=activity_name,
            description=f"https://www.strava.com/activities/{activity_id}",
        )

        # Set creation time to activity start time with safe parsing
        date_str = activity.get("start_date_local", "")
        start_time = safe_parse_date(date_str, activity_name)
        gpx.time = start_time.datetime

        # Create track and segment
        track = GPXUtils.create_track(gpx, activity_name)
        segment = GPXUtils.create_segment(track)

        # Get Strava stream data with safe access
        time_data = safe_get_nested(streams, ["time", "data"], [])
        altitude_data = safe_get_nested(streams, ["altitude", "data"], [])

        # Create track points with validation
        valid_points = 0
        for i, coords in enumerate(latlng_data):
            try:
                # Validate Strava coordinate structure [lat, lng]
                if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    continue

                lat, lng = coords[0], coords[1]

                # Validate coordinate values
                if not validate_coordinates(lat, lng):
                    logger.debug(
                        f"Invalid coordinates at point {i}: lat={lat}, lng={lng}"
                    )
                    continue

                point = gpxpy.gpx.GPXTrackPoint(
                    latitude=float(lat), longitude=float(lng)
                )

                # Add timestamp with validation (Strava time is seconds from start)
                if i < len(time_data) and isinstance(time_data[i], (int, float)):
                    try:
                        point.time = start_time.shift(seconds=time_data[i]).datetime
                    except (ValueError, OverflowError):
                        pass  # Skip invalid time offset

                # Add elevation with validation (Strava altitude in meters)
                if i < len(altitude_data) and isinstance(
                    altitude_data[i], (int, float)
                ):
                    try:
                        elevation = float(altitude_data[i])
                        if -1000 <= elevation <= 10000:  # Reasonable elevation range
                            point.elevation = elevation
                    except (ValueError, OverflowError):
                        pass  # Skip invalid elevation

                segment.points.append(point)
                valid_points += 1

            except (ValueError, TypeError, IndexError) as e:
                logger.debug(f"Skipping invalid point {i}: {e}")
                continue

        if valid_points == 0:
            logger.warning(
                f"No valid GPS points found for Strava activity {activity_id}"
            )
            return None

        logger.debug(
            f"Created GPX with {valid_points} valid points for Strava activity {activity_id}"
        )

        return gpx
