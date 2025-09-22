"""
Main CLI orchestrator combining all GPS service commands
"""

import logging

import click
from loguru import logger

from src.strava.cli import strava


class InterceptHandler(logging.Handler):
    """Redirect standard logging records to loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


@click.group()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output (DEBUG level logging).",
)
@click.version_option(version="0.1.0")
def cli(verbose: bool):
    """GPXBridge - GPS data bridge tool

    Bridge GPS data between various services like Strava, Gaia GPS, etc.
    """
    # Configure loguru for better CLI output
    logger.remove()  # Remove default handler
    log_level = "DEBUG" if verbose else "INFO"

    logging_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(handlers=[InterceptHandler()], level=logging_level, force=True)
    if verbose:
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        logging.getLogger("requests").setLevel(logging.DEBUG)

    logger.add(
        lambda msg: click.echo(msg, err=True, nl=False),
        format="{time:YYYY-MM-DD HH:mm:ss}  [<level>{level:<8}</level>]  {message}",
        level=log_level,
        colorize=True,
    )


# Add service-specific command groups
cli.add_command(strava)


if __name__ == "__main__":
    cli()
