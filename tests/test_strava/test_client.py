"""Tests for Strava API client retry and error handling."""

from typing import Callable, List

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
