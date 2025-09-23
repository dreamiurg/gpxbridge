"""Strava CLI commands."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import click
from loguru import logger

from ..common.models import ExportConfig
from .client import StravaApiClient
from .exporter import StravaExporter
from .models import ClientSettings
from .oauth import DEFAULT_SCOPE, OAuthError, run_oauth_flow


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
    default="exports",
    help="Output directory for GPX files (default: exports)",
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
@click.option(
    "--activity-type",
    type=str,
    help=(
        "Only export activities matching this Strava activity type "
        "(see Strava docs: ActivityType https://developers.strava.com/docs/ref"
        "erence/#api-models-ActivityType, SportType https://developers.strava.c"
        "om/docs/reference/#api-models-SportType)"
    ),
)
@click.option(
    "--after",
    type=str,
    metavar="ISO8601",
    help="Only include activities starting on/after this date/time",
)
@click.option(
    "--before",
    type=str,
    metavar="ISO8601",
    help="Only include activities starting before this date/time",
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
    activity_type,
    after,
    before,
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

        # Parse filters before constructing the config
        parsed_activity_type = activity_type.strip() if activity_type else None
        after_dt = _parse_iso_datetime(after, "after")
        before_dt = _parse_iso_datetime(before, "before")

        # Validate export configuration
        config = ExportConfig(
            count=count,
            output_dir=output_dir,
            delay_seconds=delay,
            organize_by_type=organize_by_type,
            resume=resume,
            activity_type=parsed_activity_type,
            after=after_dt,
            before=before_dt,
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


@strava.command()
@click.option(
    "--client-id",
    envvar="STRAVA_CLIENT_ID",
    prompt="Strava client ID",
    show_envvar=True,
    help="Strava application client ID (set STRAVA_CLIENT_ID to skip prompt)",
)
@click.option(
    "--client-secret",
    envvar="STRAVA_CLIENT_SECRET",
    prompt=True,
    hide_input=True,
    confirmation_prompt=False,
    show_envvar=True,
    help="Strava application client secret (set STRAVA_CLIENT_SECRET to skip prompt)",
)
@click.option(
    "--scope",
    default=DEFAULT_SCOPE,
    show_default=True,
    help="OAuth scopes to request during authorization",
)
@click.option(
    "--redirect-port",
    default=8721,
    show_default=True,
    type=int,
    help="Local port to capture the OAuth callback",
)
@click.option(
    "--timeout",
    default=180,
    show_default=True,
    type=int,
    help="Seconds to wait for the browser redirect",
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Do not try to open the authorization URL in a browser automatically",
)
def auth(
    client_id: str,
    client_secret: str,
    scope: str,
    redirect_port: int,
    timeout: int,
    no_browser: bool,
) -> None:
    """Guide you through Strava OAuth and print the resulting tokens."""

    try:
        tokens = run_oauth_flow(
            client_id,
            client_secret,
            scope=scope,
            port=redirect_port,
            open_browser=not no_browser,
            timeout=timeout,
        )
    except KeyboardInterrupt as exc:  # noqa: PERF203 - user interruption
        raise click.ClickException("Authorization cancelled by user") from exc
    except OAuthError as exc:
        raise click.ClickException(str(exc)) from exc

    expires_at = datetime.fromtimestamp(tokens.expires_at, tz=timezone.utc)
    click.echo()
    click.echo("Authorization successful! Save these environment variables:")
    click.echo(f'export STRAVA_CLIENT_ID="{client_id}"')
    click.echo(f'export STRAVA_CLIENT_SECRET="{client_secret}"')
    click.echo(f'export STRAVA_REFRESH_TOKEN="{tokens.refresh_token}"')
    click.echo()
    click.echo("Access token details (useful for quick testing):")
    click.echo(f"  token_type: {tokens.token_type}")
    click.echo(
        f"  access_token (expires {expires_at.isoformat()}): {tokens.access_token}"
    )
    click.echo(f"  scope: {scope}")

    athlete = tokens.athlete or {}
    if athlete:
        athlete_name = athlete.get("firstname", "") + " " + athlete.get("lastname", "")
        click.echo()
        click.echo("Authorized athlete:")
        click.echo(f"  id: {athlete.get('id', 'unknown')}")
        click.echo(f"  name: {athlete_name.strip() or 'unknown'}")

    logger.success("Strava OAuth helper completed")


def _parse_iso_datetime(value: Optional[str], label: str) -> Optional[datetime]:
    """Parse ISO8601 date/time strings passed via the CLI."""

    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise click.BadParameter(
            f"Invalid {label} value '{value}'. Use ISO 8601 format, e.g. 2024-01-01 or 2024-01-01T12:00:00Z.",
            param_hint=f"--{label}",
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed
