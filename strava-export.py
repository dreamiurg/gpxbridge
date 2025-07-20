#!/usr/bin/env python3
"""
Strava GPX Export Tool

This script exports recent activities from your Strava account as GPX files.
Since Strava API doesn't provide direct GPX export for activities, this tool
uses activity streams to reconstruct the GPX data.

Setup:
1. Create a Strava API application at https://www.strava.com/settings/api
2. Set environment variables or pass credentials via command line
3. Install required packages: pip install requests gpxpy click

Environment Variables:
- STRAVA_CLIENT_ID: Your Strava app client ID
- STRAVA_CLIENT_SECRET: Your Strava app client secret
- STRAVA_REFRESH_TOKEN: Your refresh token

Usage:
python strava-export.py --count 10 --output-dir gpx_exports
python strava-export.py --client-id ID --client-secret SECRET --refresh-token TOKEN
"""

import requests
import json
import click
import arrow
from typing import List, Dict, Optional
import gpxpy
import gpxpy.gpx
import time
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pathlib import Path
from slugify import slugify
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


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
                f"Output path '{output_dir}' outside safe area, using './gpx_exports'"
            )
            return Path("./gpx_exports").resolve()

        return path
    except (OSError, ValueError) as e:
        logger.warning(
            f"Invalid output path '{output_dir}': {e}, using './gpx_exports'"
        )
        return Path("./gpx_exports").resolve()


class StravaSettings(BaseSettings):
    """Strava API configuration using environment variables"""

    client_id: str = Field(
        ..., env="STRAVA_CLIENT_ID", description="Strava API client ID"
    )
    client_secret: str = Field(
        ..., env="STRAVA_CLIENT_SECRET", description="Strava API client secret"
    )
    refresh_token: str = Field(
        ..., env="STRAVA_REFRESH_TOKEN", description="Strava refresh token"
    )


class Activity(BaseModel):
    """Strava activity model with explicit units"""

    id: int
    name: str
    type: str
    start_date_local: str
    distance_meters: Optional[float] = None
    moving_time_seconds: Optional[int] = None
    total_elevation_gain_meters: Optional[float] = None


class RateLimitInfo(BaseModel):
    """Rate limit tracking model"""

    fifteen_min_usage: int = Field(default=0, alias="15min_usage")
    fifteen_min_limit: int = Field(default=100, alias="15min_limit")
    daily_usage: int = Field(default=0, alias="daily_usage")
    daily_limit: int = Field(default=1000, alias="daily_limit")


class StravaExporter:
    def __init__(
        self, client_id: str, client_secret: str, refresh_token: str, delay: float = 1.0
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.base_url = "https://www.strava.com/api/v3"
        self.delay = delay  # Delay between requests in seconds
        self.rate_limit_info = {
            "15min_usage": 0,
            "15min_limit": 100,
            "daily_usage": 0,
            "daily_limit": 1000,
        }

    def get_access_token(self) -> bool:
        """Exchange refresh token for access token"""
        try:
            response = requests.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            logger.success("Successfully obtained access token")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get access token: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests"""
        return {"Authorization": f"Bearer {self.access_token}"}

    def update_rate_limit_info(self, response: requests.Response):
        """Update rate limit tracking from response headers"""
        usage_header = response.headers.get("X-RateLimit-Usage")
        limit_header = response.headers.get("X-RateLimit-Limit")

        if usage_header:
            # Format: "15min_usage,daily_usage"
            try:
                parts = usage_header.split(",")
                if len(parts) >= 2:
                    self.rate_limit_info["15min_usage"] = int(parts[0].strip())
                    self.rate_limit_info["daily_usage"] = int(parts[1].strip())
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Failed to parse rate limit usage header '{usage_header}': {e}"
                )

        if limit_header:
            # Format: "15min_limit,daily_limit"
            try:
                parts = limit_header.split(",")
                if len(parts) >= 2:
                    self.rate_limit_info["15min_limit"] = int(parts[0].strip())
                    self.rate_limit_info["daily_limit"] = int(parts[1].strip())
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Failed to parse rate limit header '{limit_header}': {e}"
                )

    def check_rate_limit(self):
        """Check if we're approaching rate limits and warn user"""
        fifteen_min_pct = (
            self.rate_limit_info["15min_usage"] / self.rate_limit_info["15min_limit"]
        ) * 100
        daily_pct = (
            self.rate_limit_info["daily_usage"] / self.rate_limit_info["daily_limit"]
        ) * 100

        if fifteen_min_pct > 80:
            logger.warning(f"Using {fifteen_min_pct:.1f}% of 15-minute rate limit")
        if daily_pct > 80:
            logger.warning(f"Using {daily_pct:.1f}% of daily rate limit")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=30, min=30, max=15 * 60
        ),  # 30s, 60s, 120s, then cap at 15min
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        before_sleep=lambda retry_state: logger.info(
            f"Rate limit hit. Waiting {retry_state.next_action.sleep:.0f}s before retry {retry_state.attempt_number}/3..."
        ),
    )
    def _make_request_with_retry(
        self, url: str, params: Dict = None
    ) -> requests.Response:
        """Make HTTP request with automatic retry on rate limit errors"""
        response = requests.get(url, headers=self.get_headers(), params=params or {})

        # Update rate limit tracking
        self.update_rate_limit_info(response)

        if response.status_code == 429:
            raise requests.exceptions.HTTPError(
                "Rate limit exceeded", response=response
            )

        response.raise_for_status()
        return response

    def make_api_request(
        self, url: str, params: Dict = None
    ) -> Optional[requests.Response]:
        """Make API request with rate limiting and retry logic"""
        try:
            # Add delay between requests
            if hasattr(self, "_request_count"):
                time.sleep(self.delay)

            # Track request count for delay logic
            self._request_count = getattr(self, "_request_count", 0) + 1

            # Use tenacity-powered retry method
            response = self._make_request_with_retry(url, params)

            # Check if we're approaching limits
            self.check_rate_limit()

            return response

        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

    def get_recent_activities(self, count: int = 30) -> List[Dict]:
        """Fetch recent activities from Strava with pagination support"""
        activities = []
        page = 1
        per_page = 200  # Strava API max is 200 per page

        click.echo(
            f"Fetching {count} activities with pagination (max {per_page} per request)..."
        )

        while len(activities) < count:
            try:
                remaining = count - len(activities)
                current_per_page = min(per_page, remaining)

                click.echo(
                    f"  Requesting page {page} with {current_per_page} activities..."
                )

                response = self.make_api_request(
                    f"{self.base_url}/athlete/activities",
                    params={"per_page": current_per_page, "page": page},
                )
                if not response:
                    return activities
                page_activities = response.json()

                if not page_activities:
                    # No more activities available
                    click.echo(f"  No more activities available on page {page}")
                    break

                activities.extend(page_activities)
                click.echo(
                    f"  Retrieved {len(page_activities)} activities (total: {len(activities)})"
                )

                if len(page_activities) < current_per_page:
                    # Fewer activities returned than requested, we've reached the end
                    click.echo(
                        f"  Reached end of activities (got {len(page_activities)}, expected {current_per_page})"
                    )
                    break

                page += 1

            except requests.exceptions.RequestException as e:
                click.echo(f"✗ Failed to fetch activities: {e}", err=True)
                return activities

        # Trim to exact count requested
        activities = activities[:count]
        click.echo(f"✓ Found {len(activities)} recent activities")
        return activities

    def get_activity_streams(self, activity_id: int) -> Optional[Dict]:
        """Get activity stream data (coordinates, time, etc.)"""
        response = self.make_api_request(
            f"{self.base_url}/activities/{activity_id}/streams",
            params={
                "keys": "latlng,time,altitude,distance,heartrate,cadence,watts",
                "key_by_type": "true",
            },
        )
        if not response:
            return None
        return response.json()

    def create_gpx_from_streams(
        self, activity: Dict, streams: Dict
    ) -> Optional[gpxpy.gpx.GPX]:
        """Convert Strava activity streams to GPX format"""
        # Validate required data
        latlng_data = safe_get_nested(streams, ["latlng", "data"])
        if not latlng_data:
            activity_id = activity.get("id", "unknown")
            logger.warning(f"No GPS data available for activity {activity_id}")
            return None

        gpx = gpxpy.gpx.GPX()

        # Set GPX metadata from Strava activity with safe access
        activity_id = activity.get("id", "unknown")
        activity_name = activity.get("name", f"Activity {activity_id}")

        gpx.name = activity_name
        gpx.description = f"https://www.strava.com/activities/{activity_id}"

        # Set creation time to activity start time with safe parsing
        date_str = activity.get("start_date_local", "")
        start_time = safe_parse_date(date_str, activity_name)
        gpx.time = start_time.datetime

        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = activity_name
        gpx.tracks.append(gpx_track)

        # Create track segment
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # Get data streams with safe access
        time_data = safe_get_nested(streams, ["time", "data"], [])
        altitude_data = safe_get_nested(streams, ["altitude", "data"], [])
        # heartrate_data = safe_get_nested(streams, ["heartrate", "data"], [])  # TODO: Implement heart rate extensions

        # Create track points with validation
        valid_points = 0
        for i, coords in enumerate(latlng_data):
            try:
                # Validate coordinate structure
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

                # Add timestamp with validation
                if i < len(time_data) and isinstance(time_data[i], (int, float)):
                    try:
                        point.time = start_time.shift(seconds=time_data[i]).datetime
                    except (ValueError, OverflowError):
                        pass  # Skip invalid time offset

                # Add elevation with validation
                if i < len(altitude_data) and isinstance(
                    altitude_data[i], (int, float)
                ):
                    try:
                        elevation = float(altitude_data[i])
                        if -1000 <= elevation <= 10000:  # Reasonable elevation range
                            point.elevation = elevation
                    except (ValueError, OverflowError):
                        pass  # Skip invalid elevation

                gpx_segment.points.append(point)
                valid_points += 1

            except (ValueError, TypeError, IndexError) as e:
                logger.debug(f"Skipping invalid point {i}: {e}")
                continue

        if valid_points == 0:
            logger.warning(f"No valid GPS points found for activity {activity_id}")
            return None

        logger.debug(
            f"Created GPX with {valid_points} valid points for activity {activity_id}"
        )

        return gpx

    def export_activity_to_gpx(
        self,
        activity: Dict,
        output_dir: str = "gpx_exports",
        organize_by_type: bool = False,
    ) -> bool:
        """Export a single activity to GPX file"""
        # Safe data extraction with validation
        activity_id = activity.get("id", "unknown")
        activity_name = activity.get("name", f"Activity {activity_id}")
        activity_type = activity.get("type", "Unknown")

        # Safe date parsing
        date_str = activity.get("start_date_local", "")
        start_date = safe_parse_date(date_str, activity_name)

        click.echo(
            f"  Processing: {start_date.format('YYYY-MM-DD')} | {activity_type} | {activity_name}"
        )

        # Get activity streams
        streams = self.get_activity_streams(activity_id)
        if not streams:
            return False

        # Create GPX from streams
        gpx = self.create_gpx_from_streams(activity, streams)
        if not gpx:
            return False

        # Validate and determine final output directory
        output_path = validate_output_path(output_dir)
        if organize_by_type:
            # Create subdirectory for activity type with safe slugification
            safe_type_dir = safe_slugify(activity_type.lower(), fallback="unknown-type")
            final_output_path = output_path / safe_type_dir
        else:
            final_output_path = output_path

        # Create output directory
        try:
            final_output_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(
                f"Failed to create output directory '{final_output_path}': {e}"
            )
            return False

        # Generate filename with safe slugification
        safe_name = safe_slugify(
            activity_name, max_length=30, fallback="unnamed-activity"
        )
        safe_type = safe_slugify(activity_type, fallback="unknown-type")

        # Ensure activity_id is safe for filename
        safe_id = str(activity_id).replace("/", "-").replace("\\", "-")

        filename = (
            f"{start_date.format('YYYYMMDD')}_{safe_type}_{safe_name}_{safe_id}.gpx"
        )
        filepath = final_output_path / filename

        # Write GPX file
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(gpx.to_xml())
            click.echo(f"  ✓ Saved: {filepath}")
            return True
        except Exception as e:
            click.echo(f"  ✗ Failed to save {filepath}: {e}", err=True)
            return False

    def load_progress(self, progress_file: Path) -> Dict:
        """Load progress from file to resume interrupted exports"""
        if progress_file.exists():
            try:
                with progress_file.open("r") as f:
                    data = json.load(f)

                # Validate progress file structure
                if not isinstance(data, dict):
                    logger.warning("Progress file has invalid format, starting fresh")
                    return {"exported_activities": [], "last_activity_index": 0}

                # Ensure required fields exist with correct types
                exported_activities = data.get("exported_activities", [])
                last_activity_index = data.get("last_activity_index", 0)

                if not isinstance(exported_activities, list):
                    exported_activities = []
                if not isinstance(last_activity_index, int) or last_activity_index < 0:
                    last_activity_index = 0

                return {
                    "exported_activities": exported_activities,
                    "last_activity_index": last_activity_index,
                }

            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load progress file: {e}, starting fresh")

        return {"exported_activities": [], "last_activity_index": 0}

    def save_progress(self, progress_file: Path, progress: Dict):
        """Save export progress to file with atomic write"""
        try:
            # Use atomic write by writing to temp file first
            temp_file = progress_file.with_suffix(progress_file.suffix + ".tmp")

            with temp_file.open("w") as f:
                json.dump(progress, f, indent=2)

            # Atomic move
            temp_file.replace(progress_file)

        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")
            # Clean up temp file if it exists
            temp_file = progress_file.with_suffix(progress_file.suffix + ".tmp")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def export_recent_activities(
        self,
        count: int = 10,
        output_dir: str = "gpx_exports",
        organize_by_type: bool = False,
        resume: bool = False,
    ):
        """Export recent activities to GPX files with progress tracking"""
        if not self.get_access_token():
            return

        # Progress tracking
        progress_file = Path(output_dir) / ".strava_export_progress.json"
        progress = {"exported_activities": [], "last_activity_index": 0}

        if resume:
            progress = self.load_progress(progress_file)
            if progress["exported_activities"]:
                click.echo(
                    f"📄 Resuming export from activity {progress['last_activity_index'] + 1}"
                )

        click.echo(f"Fetching {count} recent activities...")
        activities = self.get_recent_activities(count)

        if not activities:
            click.echo("No activities found")
            return

        # Filter out already exported activities if resuming
        start_index = progress["last_activity_index"] if resume else 0
        remaining_activities = activities[start_index:]

        if not remaining_activities:
            click.echo("✓ All activities already exported")
            return

        click.echo(f"\nExporting {len(remaining_activities)} activities to GPX...")
        click.echo(f"Rate limiting: {self.delay}s delay between requests")

        success_count = len(progress["exported_activities"])
        total_activities = len(activities)

        for i, activity in enumerate(remaining_activities, start=start_index):
            activity_num = i + 1
            click.echo(
                f"\n[{activity_num}/{total_activities}] Processing activity {activity['id']}..."
            )

            if self.export_activity_to_gpx(activity, output_dir, organize_by_type):
                success_count += 1
                progress["exported_activities"].append(activity["id"])
                progress["last_activity_index"] = i

                # Save progress every 5 activities
                if len(progress["exported_activities"]) % 5 == 0:
                    self.save_progress(progress_file, progress)

            # Show rate limit status periodically
            if activity_num % 10 == 0:
                fifteen_min_pct = (
                    self.rate_limit_info["15min_usage"]
                    / self.rate_limit_info["15min_limit"]
                ) * 100
                daily_pct = (
                    self.rate_limit_info["daily_usage"]
                    / self.rate_limit_info["daily_limit"]
                ) * 100
                click.echo(
                    f"📊 Rate limit usage: {fifteen_min_pct:.1f}% (15min), {daily_pct:.1f}% (daily)"
                )

        # Clean up progress file on successful completion
        if success_count == total_activities and progress_file.exists():
            progress_file.unlink()
        else:
            self.save_progress(progress_file, progress)

        click.echo(
            f"\n✓ Successfully exported {success_count}/{total_activities} activities"
        )
        if success_count > 0:
            click.echo(f"GPX files saved in: {Path(output_dir).absolute()}")

        if success_count < total_activities:
            click.echo(
                "💡 To resume: add --resume flag to continue from where you left off"
            )


@click.command()
@click.option(
    "--client-id",
    envvar="STRAVA_CLIENT_ID",
    help="Strava API client ID (or set STRAVA_CLIENT_ID env var)",
)
@click.option(
    "--client-secret",
    envvar="STRAVA_CLIENT_SECRET",
    help="Strava API client secret (or set STRAVA_CLIENT_SECRET env var)",
)
@click.option(
    "--refresh-token",
    envvar="STRAVA_REFRESH_TOKEN",
    help="Strava refresh token (or set STRAVA_REFRESH_TOKEN env var)",
)
@click.option(
    "--count",
    default=10,
    type=int,
    help="Number of recent activities to export (default: 10)",
)
@click.option(
    "--output-dir",
    default="gpx_exports",
    help="Output directory for GPX files (default: gpx_exports)",
)
@click.option(
    "--organize-by-type",
    is_flag=True,
    help="Create subdirectories for each activity type",
)
@click.option(
    "--delay",
    default=1.0,
    type=float,
    help="Delay between requests in seconds (default: 1.0)",
)
@click.option(
    "--resume", is_flag=True, help="Resume interrupted export from where it left off"
)
def main(
    client_id,
    client_secret,
    refresh_token,
    count,
    output_dir,
    organize_by_type,
    delay,
    resume,
):
    """Export Strava activities as GPX files.

    This tool exports recent activities from your Strava account as GPX files.
    You need to provide Strava API credentials either via environment variables
    or command line options.

    Setup:
    1. Create a Strava API application at https://www.strava.com/settings/api
    2. Set environment variables or use command line options
    3. Install dependencies: pip install requests gpxpy click
    """

    # Validate CLI arguments
    validation_errors = []

    # Check credentials
    if not all([client_id, client_secret, refresh_token]):
        validation_errors.append("Missing Strava API credentials")

    # Validate count parameter
    if count <= 0:
        validation_errors.append(f"Count must be positive, got: {count}")
    if count > 10000:  # Reasonable upper limit
        validation_errors.append(f"Count too large (max 10000), got: {count}")

    # Validate delay parameter
    if delay < 0:
        validation_errors.append(f"Delay must be non-negative, got: {delay}")
    if delay > 60:  # Reasonable upper limit
        click.echo(
            f"⚠ Warning: Large delay value ({delay}s) may slow down exports significantly"
        )

    # Validate output directory
    if not output_dir or not isinstance(output_dir, str):
        validation_errors.append("Output directory must be a valid string")

    if validation_errors:
        click.echo("⚠ Validation errors found:", err=True)
        for error in validation_errors:
            click.echo(f"  - {error}", err=True)

        if not all([client_id, client_secret, refresh_token]):
            click.echo("\nOptions to provide credentials:")
            click.echo("1. Environment variables:")
            click.echo("   export STRAVA_CLIENT_ID='your_client_id'")
            click.echo("   export STRAVA_CLIENT_SECRET='your_client_secret'")
            click.echo("   export STRAVA_REFRESH_TOKEN='your_refresh_token'")
            click.echo("\n2. Command line options:")
            click.echo(
                "   python strava-export.py --client-id ID --client-secret SECRET --refresh-token TOKEN"
            )
            click.echo("\nTo get credentials:")
            click.echo("1. Go to https://www.strava.com/settings/api")
            click.echo("2. Create a new application")
            click.echo("3. Follow OAuth flow to get refresh token")

        raise click.Abort()

    # Create exporter and run with validated parameters
    try:
        exporter = StravaExporter(client_id, client_secret, refresh_token, delay=delay)
        exporter.export_recent_activities(
            count=count,
            output_dir=output_dir,
            organize_by_type=organize_by_type,
            resume=resume,
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise click.Abort()


if __name__ == "__main__":
    main()
