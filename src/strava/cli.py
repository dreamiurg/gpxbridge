"""
Strava CLI commands
"""

import click
from loguru import logger

from ..common.models import ExportConfig
from .models import ClientSettings
from .client import StravaApiClient
from .exporter import StravaExporter


@click.group()
def strava():
    """Strava GPS data export commands"""
    pass


@strava.command()
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
def export(
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

    This command exports recent activities from your Strava account as GPX files.
    You need to provide Strava API credentials either via environment variables
    or command line options.

    Setup:
    1. Create a Strava API application at https://www.strava.com/settings/api
    2. Set environment variables or use command line options
    """

    # Validate using Pydantic models
    try:
        # Validate credentials (only if all provided)
        if all([client_id, client_secret, refresh_token]):
            client_settings = ClientSettings(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
        else:
            logger.error("Missing Strava API credentials")
            logger.info(
                """Options to provide credentials:
1. Environment variables:
   export STRAVA_CLIENT_ID='your_client_id'
   export STRAVA_CLIENT_SECRET='your_client_secret'
   export STRAVA_REFRESH_TOKEN='your_refresh_token'

2. Command line options:
   gpxbridge strava export --client-id ID --client-secret SECRET --refresh-token TOKEN

To get credentials:
1. Go to https://www.strava.com/settings/api
2. Create a new application
3. Follow OAuth flow to get refresh token"""
            )
            raise click.Abort()

        # Validate export configuration
        config = ExportConfig(
            count=count,
            output_dir=output_dir,
            delay_seconds=delay,
            organize_by_type=organize_by_type,
            resume=resume,
        )

        # Show warning for large delay values
        if delay > 60:
            logger.warning(
                f"Large delay value ({delay}s) may slow down exports significantly"
            )

    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise click.Abort()

    # Create client and exporter
    try:
        client = StravaApiClient(
            client_settings.client_id,
            client_settings.client_secret,
            client_settings.refresh_token,
            delay=delay,
        )
        exporter = StravaExporter(client)
        exporter.export_recent_activities(config)

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise click.Abort()
