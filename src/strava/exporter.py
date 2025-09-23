"""
Strava export orchestration and file management
"""

import json
from pathlib import Path
from typing import Any, Dict
from loguru import logger

from ..common.models import ProgressData, ExportConfig
from ..common.utils import validate_output_path, safe_slugify, safe_parse_date
from .client import StravaApiClient
from .gpx_converter import StravaGPXConverter
from .models import StravaActivity


class StravaExporter:
    """Orchestrates Strava activity exports to GPX files"""

    def __init__(self, client: StravaApiClient):
        self.client = client

    def export_activity_to_gpx(
        self,
        activity: Dict[str, Any],
        output_dir: str = "exports",
        organize_by_type: bool = False,
    ) -> bool:
        """Export a single Strava activity to GPX file"""
        # Validate activity data with Pydantic
        try:
            strava_activity = StravaActivity(**activity)
        except Exception as e:
            logger.error(f"Invalid activity data: {e}")
            return False

        # Safe data extraction
        activity_id = strava_activity.id
        activity_name = strava_activity.name
        activity_type = strava_activity.type

        # Safe date parsing
        start_date = safe_parse_date(strava_activity.start_date_local, activity_name)

        logger.info(
            f"Processing: {start_date.format('YYYY-MM-DD')} | {activity_type} | {activity_name}"
        )

        # Get activity streams
        streams = self.client.get_activity_streams(activity_id)
        if not streams:
            return False

        # Create GPX from Strava streams
        gpx = StravaGPXConverter.create_gpx_from_strava_streams(activity, streams)
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
            logger.success(f"Saved: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")
            return False

    def load_progress(self, progress_file: Path) -> ProgressData:
        """Load progress from file to resume interrupted exports"""
        if progress_file.exists():
            try:
                with progress_file.open("r") as f:
                    data = json.load(f)

                # Validate using Pydantic model
                progress_data = ProgressData(**data)
                return progress_data

            except (OSError, json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to load progress file: {e}, starting fresh")

        return ProgressData()

    def save_progress(self, progress_file: Path, progress: ProgressData) -> None:
        """Save export progress to file with atomic write"""
        try:
            # Use atomic write by writing to temp file first
            temp_file = progress_file.with_suffix(progress_file.suffix + ".tmp")

            with temp_file.open("w") as f:
                json.dump(progress.model_dump(), f, indent=2)

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

    def export_recent_activities(self, config: ExportConfig):
        """Export recent activities to GPX files with progress tracking"""
        if not self.client.get_access_token():
            return

        # Progress tracking
        progress_file = Path(config.output_dir) / ".strava_export_progress.json"
        config_signature = config.progress_signature()
        progress = ProgressData(config_signature=config_signature)

        if config.resume:
            existing_progress = self.load_progress(progress_file)
            if (
                existing_progress.config_signature
                and existing_progress.config_signature != config_signature
            ):
                logger.warning(
                    "Progress file filters differ from current request; starting fresh"
                )
            else:
                progress = existing_progress
                progress.config_signature = config_signature
                if progress.exported_activities:
                    logger.info(
                        f"Resuming export from activity {progress.last_activity_index + 1}"
                    )

        logger.info(f"Fetching {config.count} recent activities...")
        activities = self.client.get_recent_activities(
            config.count,
            after=config.after,
            before=config.before,
            activity_type=config.activity_type,
        )

        if not activities:
            if config.activity_type or config.after or config.before:
                logger.warning("No activities matched the requested filters")
            else:
                logger.warning("No activities found")
            return

        # Filter out already exported activities if resuming
        start_index = progress.last_activity_index if config.resume else 0
        remaining_activities = activities[start_index:]

        if not remaining_activities:
            logger.success("All activities already exported")
            return

        logger.info(f"Exporting {len(remaining_activities)} activities to GPX...")
        logger.info(f"Rate limiting: {config.delay_seconds}s delay between requests")

        success_count = len(progress.exported_activities)
        total_activities = len(activities)

        for i, activity in enumerate(remaining_activities, start=start_index):
            activity_num = i + 1
            activity_id = int(activity["id"])
            logger.info(
                f"[{activity_num}/{total_activities}] Processing activity {activity_id}..."
            )

            if self.export_activity_to_gpx(
                activity, config.output_dir, config.organize_by_type
            ):
                success_count += 1
                progress.exported_activities.append(activity_id)
                progress.last_activity_index = i
                progress.config_signature = config_signature

                # Save progress every 5 activities
                if len(progress.exported_activities) % 5 == 0:
                    self.save_progress(progress_file, progress)

            # Show rate limit status periodically
            if activity_num % 10 == 0:
                fifteen_min_pct = (
                    self.client.rate_limit_info.fifteen_min_usage
                    / self.client.rate_limit_info.fifteen_min_limit
                ) * 100
                daily_pct = (
                    self.client.rate_limit_info.daily_usage
                    / self.client.rate_limit_info.daily_limit
                ) * 100
                logger.info(
                    f"Rate limit usage: {fifteen_min_pct:.1f}% (15min), {daily_pct:.1f}% (daily)"
                )

        # Clean up progress file on successful completion
        if success_count == total_activities and progress_file.exists():
            progress_file.unlink()
        else:
            self.save_progress(progress_file, progress)

        logger.success(
            f"Successfully exported {success_count}/{total_activities} activities"
        )
        if success_count > 0:
            logger.info(f"GPX files saved in: {Path(config.output_dir).absolute()}")

        if success_count < total_activities:
            logger.info(
                "To resume: add --resume flag to continue from where you left off"
            )
