"""Tests for Strava API client retry and error handling."""

from datetime import datetime, timezone
from typing import Callable, Dict, List

import pytest
import requests
from loguru import logger as loguru_logger

from src.strava.client import StravaApiClient


def _make_response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = b"{}"
    response.url = "https://www.strava.com/api/v3/test"
    response.request = requests.Request(method="GET", url=response.url).prepare()
    return response


@pytest.fixture(autouse=True)
def _enable_loguru():
    """Enable loguru logging for src modules during tests."""

    loguru_logger.enable("src")
    yield
    loguru_logger.disable("src")


def _capture_logs(level: str) -> Callable[[], List[str]]:
    captured: List[str] = []

    sink_id = loguru_logger.add(
        lambda message: captured.append(str(message)), level=level
    )

    def finalize() -> List[str]:
        loguru_logger.remove(sink_id)
        return captured

    return finalize


def test_make_api_request_unauthorized_does_not_retry(monkeypatch):
    client = StravaApiClient("id", "secret", "refresh", delay=0)
    client.access_token = "token"

    unauthorized_response = _make_response(401)
    calls: List[int] = []

    def fake_get(url, headers=None, params=None):
        calls.append(1)
        return unauthorized_response

    monkeypatch.setattr(requests, "get", fake_get)

    collect_logs = _capture_logs("ERROR")

    try:
        result = client.make_api_request(
            "https://www.strava.com/api/v3/athlete/activities"
        )
    finally:
        logs = collect_logs()

    assert result is None
    assert len(calls) == 1
    assert any("Unauthorized response from Strava API" in log for log in logs)


def test_make_api_request_rate_limit_retries(monkeypatch):
    client = StravaApiClient("id", "secret", "refresh", delay=0)
    client.access_token = "token"

    rate_limited_response = _make_response(429)
    calls: List[int] = []

    def fake_get(url, headers=None, params=None):
        calls.append(1)
        return rate_limited_response

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(
        StravaApiClient._make_request_with_retry.retry,
        "sleep",
        lambda duration, *_args, **_kwargs: None,
    )

    collect_info_logs = _capture_logs("INFO")
    collect_error_logs = _capture_logs("ERROR")

    try:
        result = client.make_api_request(
            "https://www.strava.com/api/v3/athlete/activities"
        )
    finally:
        info_logs = collect_info_logs()
        error_logs = collect_error_logs()

    assert result is None
    assert len(calls) == 3
    assert any("Rate limit hit" in log for log in info_logs)
    assert any("Strava rate limit exceeded" in log for log in error_logs)


def test_get_recent_activities_filters_by_type(monkeypatch):
    client = StravaApiClient("id", "secret", "refresh", delay=0)
    client.access_token = "token"

    pages = [
        [
            {"id": 1, "type": "Ride"},
            {"id": 2, "type": "Run"},
        ],
        [
            {"id": 3, "sport_type": "Run"},
        ],
    ]

    def fake_make_api_request(url, params=None):
        payload = pages.pop(0) if pages else []

        class _Response:
            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        return _Response(payload)

    monkeypatch.setattr(client, "make_api_request", fake_make_api_request)

    activities = client.get_recent_activities(2, activity_type="Run")

    assert [activity["id"] for activity in activities] == [2, 3]


def test_get_recent_activities_applies_date_params(monkeypatch):
    client = StravaApiClient("id", "secret", "refresh", delay=0)
    client.access_token = "token"

    captured_params: List[Dict[str, int]] = []

    def fake_make_api_request(url, params=None):
        captured_params.append(params or {})

        class _Response:
            def json(self):
                return []

        return _Response()

    monkeypatch.setattr(client, "make_api_request", fake_make_api_request)

    after = datetime(2024, 1, 1, tzinfo=timezone.utc)
    before = datetime(2024, 2, 1, tzinfo=timezone.utc)

    client.get_recent_activities(count=5, after=after, before=before)

    assert captured_params
    params = captured_params[0]
    assert params["after"] == int(after.timestamp())
    assert params["before"] == int(before.timestamp())
