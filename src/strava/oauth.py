"""Utilities to drive Strava OAuth authorization flows."""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from jinja2 import Environment, PackageLoader, TemplateNotFound, select_autoescape
from loguru import logger

DEFAULT_SCOPE = "activity:read_all"
DEFAULT_TIMEOUT = 180
_DEFAULT_EXPORT_COMMAND = "uv run gpxbridge strava export --count 5 --output-dir ./exports"

_TEMPLATE_ENV: Environment | None = None


class OAuthError(RuntimeError):
    """Raised when the Strava OAuth flow fails."""


@dataclass
class OAuthTokens:
    """Container for tokens returned by Strava."""

    access_token: str
    refresh_token: str
    expires_at: int
    expires_in: int
    token_type: str
    athlete: Dict[str, Any]

    @classmethod
    def from_response(cls, payload: Dict[str, Any]) -> "OAuthTokens":
        try:
            return cls(
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                expires_at=int(payload["expires_at"]),
                expires_in=int(payload["expires_in"]),
                token_type=str(payload.get("token_type", "Bearer")),
                athlete=dict(payload.get("athlete", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OAuthError(
                "Unexpected response while exchanging OAuth code for tokens"
            ) from exc


def _get_template_env() -> Environment:
    """Return a cached Jinja environment for OAuth templates."""

    global _TEMPLATE_ENV
    if _TEMPLATE_ENV is None:
        _TEMPLATE_ENV = Environment(
            loader=PackageLoader("src.strava", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _TEMPLATE_ENV


def _render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a template and surface missing template errors as OAuth issues."""

    try:
        template = _get_template_env().get_template(template_name)
    except TemplateNotFound as exc:
        raise OAuthError(f"Missing OAuth template: {template_name}") from exc
    return template.render(**context)


def _build_authorization_url(
    client_id: str, redirect_uri: str, scope: str, state: str
) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",
        "scope": scope,
        "state": state,
    }
    encoded = urlencode(params)
    return f"https://www.strava.com/oauth/authorize?{encoded}"


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth `code` query parameter."""

    server_version = "StravaOAuthHelper/1.0"
    error_content_type = "text/html"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - signature fixed
        # Silence BaseHTTPRequestHandler's noisy logging
        logger.debug("OAuth callback server: " + format % args)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        server: "_OAuthHTTPServer" = self.server  # type: ignore[assignment]
        parsed = urlparse(self.path)

        if parsed.path not in ("/", "", "/callback"):
            self.send_error(404, "Unknown path")
            return

        params = parse_qs(parsed.query)
        state = params.get("state", [None])[0]
        if state != server.expected_state:
            logger.error("Received OAuth callback with unexpected state: {}", state)
            self.send_error(400, "State mismatch. Please retry the authorization.")
            return

        if "error" in params:
            error_code = params.get("error", ["unknown"])[0]
            logger.error("User denied OAuth authorization: {}", error_code)
            self._write_html(
                200,
                "<h1>Authorization cancelled</h1><p>You can close this window.</p>",
            )
            server.error = OAuthError(
                "Authorization was cancelled. Re-run the helper to try again."
            )
            server.signal.set()
            return

        code = params.get("code", [None])[0]
        if not code:
            logger.error("OAuth callback missing authorization code")
            self.send_error(
                400, "Missing authorization code. Please retry the authorization."
            )
            return

        try:
            tokens = _exchange_code_for_tokens(
                server.client_id, server.client_secret, str(code)
            )
        except OAuthError as exc:
            logger.error("Token exchange failed during OAuth callback: {}", exc)
            server.error = exc
            server.signal.set()
            self._write_html(200, _render_error_html(str(exc)))
            return

        server.authorization_code = str(code)
        server.tokens = tokens
        server.signal.set()
        self._write_html(
            200,
            _render_success_html(server.client_id, server.client_secret, tokens),
        )

    def _write_html(self, status: int, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _OAuthHTTPServer(HTTPServer):
    """HTTP server that captures the OAuth authorization code."""

    def __init__(
        self,
        address: tuple[str, int],
        expected_state: str,
        client_id: str,
        client_secret: str,
    ):
        super().__init__(address, _OAuthCallbackHandler)
        self.expected_state = expected_state
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_code: Optional[str] = None
        self.tokens: Optional[OAuthTokens] = None
        self.signal = threading.Event()
        self.error: Optional[Exception] = None


def _wait_for_callback(server: _OAuthHTTPServer, timeout: int) -> None:
    logger.info(
        "Waiting for Strava to redirect back with an authorization code (timeout={}s)",
        timeout,
    )
    if not server.signal.wait(timeout=timeout):
        raise OAuthError(
            "Timed out waiting for Strava authorization. Did you approve the app?"
        )

    if server.error:
        raise server.error

    if not server.authorization_code:
        raise OAuthError(
            "Did not receive an authorization code from Strava. Please try again."
        )


def _run_callback_server(
    client_id: str, client_secret: str, port: int, state: str, timeout: int
) -> tuple[str, Optional[OAuthTokens]]:
    server = _OAuthHTTPServer(("localhost", port), state, client_id, client_secret)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        _wait_for_callback(server, timeout)
        if not server.authorization_code:
            raise OAuthError(
                "Did not receive an authorization code from Strava. Please try again."
            )
        return server.authorization_code, server.tokens
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _exchange_code_for_tokens(
    client_id: str, client_secret: str, code: str
) -> OAuthTokens:
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(token_url, data=payload, timeout=30)
        response.raise_for_status()
        logger.success("Successfully exchanged authorization code for tokens")
        data = response.json()
        sanitized_payload: Dict[str, Any] = {}
        for key, value in data.items():
            if "token" in key.lower():
                sanitized_payload[key] = "<redacted>"
            elif key == "athlete" and isinstance(value, dict):
                sanitized_payload[key] = {
                    field: value[field]
                    for field in ("id", "firstname", "lastname")
                    if field in value
                }
            else:
                sanitized_payload[key] = value
        logger.debug(
            "Token exchange response (sanitized): {}",
            json.dumps(sanitized_payload, indent=2),
        )
        return OAuthTokens.from_response(data)
    except requests.exceptions.RequestException as exc:
        raise OAuthError(
            "Failed to exchange authorization code for tokens: {}".format(exc)
        ) from exc


def run_oauth_flow(
    client_id: str,
    client_secret: str,
    *,
    scope: str = DEFAULT_SCOPE,
    port: int = 8721,
    open_browser: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
) -> OAuthTokens:
    """Run a Strava OAuth dance and return refresh/access tokens."""

    state = secrets.token_urlsafe(16)
    redirect_uri = f"http://localhost:{port}"
    auth_url = _build_authorization_url(client_id, redirect_uri, scope, state)

    logger.info("Starting Strava OAuth flow")
    logger.info("Authorization URL: {}", auth_url)

    if open_browser:
        logger.info("Opening browser for authorization...")
        try:
            import webbrowser

            webbrowser.open(auth_url, new=1, autoraise=True)
        except Exception as exc:  # noqa: BLE001 - best effort
            logger.warning("Failed to open browser automatically: {}", exc)
            logger.warning("Copy the URL above into your browser to continue.")
    else:
        logger.info("Open the URL above in your browser to authorize access.")

    try:
        code, tokens = _run_callback_server(
            client_id, client_secret, port, state, timeout
        )
    except OSError as exc:
        raise OAuthError(
            f"Could not start local callback server on port {port}: {exc}"
        ) from exc
    logger.info("Received authorization code from Strava; completing flow")
    if tokens is None:
        tokens = _exchange_code_for_tokens(client_id, client_secret, code)
    return tokens


def _render_success_html(
    client_id: str, client_secret: str, tokens: OAuthTokens
) -> str:
    env_exports = [
        f'export STRAVA_CLIENT_ID="{client_id}"',
        f'export STRAVA_CLIENT_SECRET="{client_secret}"',
        f'export STRAVA_REFRESH_TOKEN="{tokens.refresh_token}"',
    ]
    expires_at_iso = datetime.fromtimestamp(
        tokens.expires_at, tz=timezone.utc
    ).isoformat()

    context: Dict[str, Any] = {
        "env_exports": env_exports,
        "export_command": _DEFAULT_EXPORT_COMMAND,
        "expires_at": expires_at_iso,
        "athlete": tokens.athlete or {},
    }
    return _render_template("oauth_success.html", context)


def _render_error_html(message: str) -> str:
    return _render_template("oauth_error.html", {"message": message})


__all__ = ["run_oauth_flow", "OAuthTokens", "OAuthError", "DEFAULT_SCOPE"]
