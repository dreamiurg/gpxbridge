"""
Main CLI orchestrator combining all GPS service commands
"""

import click
from loguru import logger

from src.strava.cli import strava


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """GPXBridge - GPS data bridge tool

    Bridge GPS data between various services like Strava, Gaia GPS, etc.
    """
    # Configure loguru for better CLI output
    logger.remove()  # Remove default handler
    logger.add(
        lambda msg: click.echo(msg, err=True),
        format="<level>{level: <8}</level> | {message}",
        level="INFO",
        colorize=True,
    )


# Add service-specific command groups
cli.add_command(strava)


if __name__ == "__main__":
    cli()
