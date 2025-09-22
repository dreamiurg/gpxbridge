"""
Strava API client with authentication and rate limiting
"""

import requests
import time
from typing import Dict, List, Optional
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .models import RateLimitInfo


class StravaApiClient:
    """Strava API client with OAuth and rate limiting"""

    def __init__(
        self, client_id: str, client_secret: str, refresh_token: str, delay: float = 1.0
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.base_url = "https://www.strava.com/api/v3"
        self.delay = delay  # Delay between requests in seconds
        self.rate_limit_info = RateLimitInfo()

    def get_access_token(self) -> bool:
        """Exchange refresh token for access token"""
        try:
            token_url = "https://www.strava.com/oauth/token"
            logger.debug(
                "POST {} (grant_type=refresh_token, client_id={})",
                token_url,
                self.client_id,
            )
            response = requests.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            logger.success("Successfully obtained access token")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get access token: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests"""
        return {"Authorization": f"Bearer {self.access_token}"}

    def update_rate_limit_info(self, response: requests.Response):
        """Update rate limit tracking from response headers"""
        usage_header = response.headers.get("X-RateLimit-Usage")
        limit_header = response.headers.get("X-RateLimit-Limit")

        try:
            update_data = {}

            if usage_header:
                # Format: "15min_usage,daily_usage"
                parts = usage_header.split(",")
                if len(parts) >= 2:
                    update_data["fifteen_min_usage"] = int(parts[0].strip())
                    update_data["daily_usage"] = int(parts[1].strip())

            if limit_header:
                # Format: "15min_limit,daily_limit"
                parts = limit_header.split(",")
                if len(parts) >= 2:
                    update_data["fifteen_min_limit"] = int(parts[0].strip())
                    update_data["daily_limit"] = int(parts[1].strip())

            if update_data:
                # Update with validated data
                current_data = self.rate_limit_info.model_dump()
                current_data.update(update_data)
                self.rate_limit_info = RateLimitInfo(**current_data)

        except (ValueError, AttributeError, Exception) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")

    def check_rate_limit(self):
        """Check if we're approaching rate limits and warn user"""
        fifteen_min_pct = (
            self.rate_limit_info.fifteen_min_usage
            / self.rate_limit_info.fifteen_min_limit
        ) * 100
        daily_pct = (
            self.rate_limit_info.daily_usage / self.rate_limit_info.daily_limit
        ) * 100

        if fifteen_min_pct > 80:
            logger.warning(f"Using {fifteen_min_pct:.1f}% of 15-minute rate limit")
        if daily_pct > 80:
            logger.warning(f"Using {daily_pct:.1f}% of daily rate limit")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=30, min=30, max=15 * 60
        ),  # 30s, 60s, 120s, then cap at 15min
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        before_sleep=lambda retry_state: logger.info(
            f"Rate limit hit. Waiting {retry_state.next_action.sleep:.0f}s before retry {retry_state.attempt_number}/3..."
        ),
    )
    def _make_request_with_retry(
        self, url: str, params: Dict = None
    ) -> requests.Response:
        """Make HTTP request with automatic retry on rate limit errors"""
        logger.debug("GET {} params={} ", url, params or {})
        response = requests.get(url, headers=self.get_headers(), params=params or {})
        logger.debug(
            "Response {} {} for GET {}",
            response.status_code,
            response.reason,
            url,
        )

        # Update rate limit tracking
        self.update_rate_limit_info(response)

        if response.status_code == 429:
            raise requests.exceptions.HTTPError(
                "Rate limit exceeded", response=response
            )

        response.raise_for_status()
        return response

    def make_api_request(
        self, url: str, params: Dict = None
    ) -> Optional[requests.Response]:
        """Make API request with rate limiting and retry logic"""
        try:
            # Add delay between requests
            if hasattr(self, "_request_count"):
                logger.debug("Sleeping {:.2f}s before request", self.delay)
                time.sleep(self.delay)

            # Track request count for delay logic
            self._request_count = getattr(self, "_request_count", 0) + 1

            # Use tenacity-powered retry method
            response = self._make_request_with_retry(url, params)

            # Check if we're approaching limits
            self.check_rate_limit()

            return response

        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

    def get_recent_activities(self, count: int = 30) -> List[Dict]:
        """Fetch recent activities from Strava with pagination support"""
        activities = []
        page = 1
        per_page = 200  # Strava API max is 200 per page

        logger.info(
            f"Fetching {count} activities with pagination (max {per_page} per request)..."
        )

        while len(activities) < count:
            try:
                remaining = count - len(activities)
                current_per_page = min(per_page, remaining)

                logger.info(
                    f"  Requesting page {page} with {current_per_page} activities..."
                )

                response = self.make_api_request(
                    f"{self.base_url}/athlete/activities",
                    params={"per_page": current_per_page, "page": page},
                )
                if not response:
                    return activities
                page_activities = response.json()

                if not page_activities:
                    # No more activities available
                    logger.info(f"  No more activities available on page {page}")
                    break

                activities.extend(page_activities)
                logger.info(
                    f"  Retrieved {len(page_activities)} activities (total: {len(activities)})"
                )

                if len(page_activities) < current_per_page:
                    # Fewer activities returned than requested, we've reached the end
                    logger.info(
                        f"  Reached end of activities (got {len(page_activities)}, expected {current_per_page})"
                    )
                    break

                page += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to fetch activities: {e}")
                return activities

        # Trim to exact count requested
        activities = activities[:count]
        logger.success(f"Found {len(activities)} recent activities")
        return activities

    def get_activity_streams(self, activity_id: int) -> Optional[Dict]:
        """Get activity stream data (coordinates, time, etc.)"""
        response = self.make_api_request(
            f"{self.base_url}/activities/{activity_id}/streams",
            params={
                "keys": "latlng,time,altitude,distance,heartrate,cadence,watts",
                "key_by_type": "true",
            },
        )
        if not response:
            return None
        return response.json()
