# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPXBridge offers a CLI to bridge GPS data between various services (currently Strava). The project is built with Python 3.13+ using modern tools like uv for dependency management.

## Common Development Commands

### Package Management
- `uv add <package>` - Add a new dependency
- `uv add --dev <package>` - Add a development dependency
- `uv run <command>` - Run commands in the virtual environment

### Code Quality
- `uv run ruff check` - Run linting (ruff is included as a project dependency)
- `uv run ruff format` - Format code
- `uv run mypy src/` - Type checking
- `uv run pytest` - Run tests

### Application Usage
- `uv run gpxbridge --help` - Show available commands
- `uv run gpxbridge strava export --help` - Show Strava export options
- `uv run gpxbridge strava export --count 5 --output-dir ./exports` - Export 5 recent Strava activities

## Architecture

### Project Structure
- `src/cli.py` - Main CLI orchestrator that combines service-specific commands
- `src/common/` - Shared models, utilities, and GPX handling across all GPS services
- `src/strava/` - Strava-specific implementation (API client, exporter, models)
- `data/` - Sample exported GPX files organized by activity type

### Key Components

**Service Plugin Architecture**: The CLI uses a modular design where each GPS service (Strava, Gaia GPS, etc.) registers its commands with the main CLI. Service-specific commands are in `src/<service>/cli.py`.

**Pydantic Models**: All data validation uses Pydantic models for robust input validation and type safety. Common models in `src/common/models.py`, service-specific in `src/<service>/models.py`.

**Export Pipeline**:
1. API client fetches activity metadata (`client.py`)
2. Streams/GPS data retrieved for each activity
3. GPX converter transforms service data to standard GPX format (`gpx_converter.py`)
4. Exporter orchestrates the process with progress tracking (`exporter.py`)

**Security Features**:
- Path traversal protection in `validate_output_path()`
- Safe slugification for filenames
- Input validation for all user-provided data
- Atomic file operations for progress tracking

## Important Implementation Notes

- **Rate Limiting**: Strava API has strict rate limits (600 requests per 15 minutes, 100 per day). The client implements automatic rate limiting with configurable delays.

- **Resume Functionality**: Exports can be resumed from interruption using progress files (`.strava_export_progress.json`).

- **Error Handling**: Comprehensive error handling with fallbacks for invalid data, network issues, and file operations.

- **File Organization**: Activities can be organized by type into subdirectories using the `--organize-by-type` flag.

## Credential Management

Strava API credentials are provided via environment variables:
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

The application validates all credentials before starting exports and provides helpful setup instructions when credentials are missing.
