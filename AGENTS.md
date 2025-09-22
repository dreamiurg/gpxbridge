# AGENTS.md

Guidance for Codex (and other code-focused agents) working in this repository.

## Project Snapshot
- **Name**: GPXBridge – Python 3.13+ CLI that syncs GPS activity data between services (currently Strava).
- **Tooling**: [`uv`](https://github.com/astral-sh/uv) drives dependency management, virtualenvs, and command execution.
- **Goal**: Fetch activities from connected services, normalize them to GPX, and export them locally.

## Quick Start
1. Install in editable mode: `uv sync`
2. Check the CLI: `uv run gpxbridge --help`
3. Export Strava activities: `uv run gpxbridge strava export --count 5 --output-dir ./exports`

## Everyday Commands
### Package & Env
- `uv add <pkg>` – Add runtime dependency
- `uv add --dev <pkg>` – Add development dependency
- `uv run <cmd>` – Execute commands inside the managed environment

### Quality Gates
- `uv run ruff check` – Linting
- `uv run ruff format` – Formatting
- `uv run mypy src/` – Static typing
- `uv run pytest` – Test suite
- `uv run pytest --cov` – Tests with coverage
- `uv run pytest -m "not slow"` – Skip slow tests
- `uv run pytest tests/test_common/` – Targeted module tests
- `uv run pytest -k "test_coordinate"` – Name-filtered run

## Repository Structure
- `src/cli.py` – Entry point that wires per-service subcommands
- `src/common/` – GPX utilities, shared models, helpers
- `src/strava/` – Strava client, exporter, and CLI glue
- `data/` – Sample GPX exports grouped by activity type

### Architectural Highlights
- **Plugin-style CLI** – Each service owns `src/<service>/cli.py` and registers commands with the main CLI.
- **Pydantic Models** – Shared schemas live in `src/common/models.py`; service-specific schemas in `src/<service>/models.py`.
- **Export Pipeline** – Fetch metadata → pull activity streams → convert to GPX via `gpx_converter.py` → orchestrate with `exporter.py`.
- **Safety** – Output paths validated (`validate_output_path()`), filenames slugified, operations guarded with atomic writes.

## Implementation Notes
- **Strava Rate Limits** – Respect 600 requests per 15 minutes and 100 per day. Client already throttles; avoid unnecessary API calls.
- **Resume Support** – Exports can restart using `.strava_export_progress.json` progress files.
- **Error Strategy** – Defensive handling for malformed data, network hiccups, and filesystem failures.
- **Activity Organization** – `--organize-by-type` can group exports into per-activity folders.

## Git Expectations
- Never run `git commit`, `git push`, or any other Git command that mutates history or the working tree unless the user explicitly instructs you to do so.
- Run linting and tests before committing when possible; report if you must skip.

## Credentials
Set the following environment variables for Strava access before running exports:
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

The app validates credentials on startup and provides guidance if they are missing.

## Agent Checklist
- Understand the task, clarify uncertainties, and document assumptions in replies.
- Prefer `uv run …` for tooling. Avoid out-of-band managers unless instructed.
- Use the `gh` CLI for any GitHub-facing workflows (issues, PRs, releases) unless the user requests a different tool.
- After code changes, always run the project’s pre-commit hooks and full test suite; address any failures before reporting back unless the user directs otherwise.
- Pre-commit hooks run Ruff (lint + format) and `uv run mypy src/`; expect commits to fail if lint or typing regress.
- Keep instructions in this file aligned with Codex behaviour; update them if workflows change.
