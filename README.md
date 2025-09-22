# GPXBridge?

GPXBridge is a Python command-line tool that pulls your recent GPS activities from Strava and saves them as GPX files you can archive or import into other services.

## Why GPXBridge?

Once upon a time I wanted to import all of my hike routes to Gaia, but could not find a convinient way to do that, so I cracked the Claude/Codex AI whip to create GPXBridge.

## Install & Verify
```bash
uv sync
uv run gpxbridge --help
```

## Configure Strava Access
GPXBridge needs a Strava API application and an OAuth refresh token in order to download your activities. You only have to do this setup once.

### 1. Create a Strava API Application
1. Sign in at <https://www.strava.com/settings/api>.
2. Click **Create or Manage your Applications** and create a new app.
3. Give it a name (e.g., "GPXBridge"), set a website (any URL you control), and use `http://localhost` as the Authorization Callback Domain.
4. Save. You will now see your **Client ID** and **Client Secret**.

### 2. Authorize Yourself and Capture a Refresh Token

Run the built-in helper to guide you through the OAuth dance:

```bash
uv run gpxbridge strava auth
```

The command prompts for your client ID/secret (or reads `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`), opens Strava's authorization page, and listens on `http://localhost:8721` for the redirect. When you approve the app it prints ready-to-copy exports for `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_REFRESH_TOKEN`.

Prefer the manual route? Follow the original flow:

1. Visit this authorization URL in your browser, replacing `YOUR_CLIENT_ID` with the number you just received:
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all
   ```
2. Approve the permissions. Strava will redirect you to `http://localhost/?code=...`. Copy the long `code` value from the address bar.
3. Exchange that code for an access + refresh token using `curl` (replace placeholders before running):
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=THE_CODE_FROM_STEP_2 \
     -d grant_type=authorization_code
   ```
4. The JSON response contains `access_token`, `refresh_token`, and `expires_at`. Copy the `refresh_token` value—GPXBridge uses it to request fresh access tokens automatically.

### 3. Provide Credentials to GPXBridge
Set these environment variables in the shell you plan to use:
```bash
export STRAVA_CLIENT_ID="your-client-id"
export STRAVA_CLIENT_SECRET="your-client-secret"
export STRAVA_REFRESH_TOKEN="your-refresh-token"
```
You can also pass them as flags on every run (`--client-id`, `--client-secret`, `--refresh-token`), but exporting them once per shell session is usually easier.

## Export Activities
The CLI exposes a Strava command group with an `export` subcommand.

### Basic Exports
```bash
uv run gpxbridge strava export --count 5 --output-dir ./exports
```
This fetches your five most recent activities and writes GPX files into `./exports`. If the folder doesn’t exist, GPXBridge creates it.

### Helpful Options
- `--organize-by-type` – place activities into subfolders such as `run/` or `ride/`
- `--delay 2.5` – add extra seconds between API calls when you are close to rate limits
- `--resume` – resume an interrupted run using `.strava_export_progress.json` inside the export folder
- `--count 50` – raise or lower how many activities to fetch per run

You can mix options as needed:
```bash
uv run gpxbridge strava export \
  --count 25 \
  --output-dir ~/gpx-backups \
  --organize-by-type \
  --resume
```

### Checking Available Commands
```bash
uv run gpxbridge --help
uv run gpxbridge strava --help
uv run gpxbridge strava export --help
```
Each level prints descriptions of the available flags and defaults.

## Troubleshooting
- **Missing credentials**: The CLI exits early and prints setup instructions. Double-check environment variables are present in the same shell where you run `uv run`.
- **Invalid redirect URI**: Ensure the Authorization Callback Domain on Strava is exactly `localhost` (no protocol, no trailing slash).
- **Rate limit warnings**: GPXBridge surfaces usage in the logs. Re-run later or increase `--delay`.
- **Partial exports**: Use `--resume` to pick up where you left off. The progress file lives alongside your GPX files.

Happy exporting!
