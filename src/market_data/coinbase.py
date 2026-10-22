"""Client for the Coinbase Exchange public candles endpoint (one window per call)."""
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests

BASE_URL = "https://api.exchange.coinbase.com"
HEADERS = {"User-Agent": "market-data-platform/0.1"}
# Temporary problems worth retrying: rate limit (429) and server errors (5xx)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def build_candles_params(
    window_start: datetime, window_end: datetime, granularity_seconds: int = 3600
) -> dict:
    """Translate our window [start, end) into Coinbase query parameters."""
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("window_start and window_end must be timezone-aware (use UTC)")
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")

    # Coinbase treats `end` as inclusive, but our windows exclude the end.
    # So we ask for the start of the LAST candle we want, not for the window end.
    last_candle_start = window_end - timedelta(seconds=granularity_seconds)
    return {
        "granularity": granularity_seconds,
        "start": window_start.astimezone(UTC).strftime(TIMESTAMP_FORMAT),
        "end": last_candle_start.astimezone(UTC).strftime(TIMESTAMP_FORMAT),
    }


def fetch_candles_window(
    product_id: str,
    window_start: datetime,
    window_end: datetime,
    granularity_seconds: int = 3600,
    max_attempts: int = 4,
    backoff_seconds: float = 1.0,
    get: Callable = requests.get,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list]:
    """Fetch the raw candles of one window, retrying temporary failures.

    `get` and `sleep` can be replaced in tests, so no real network or waiting is needed.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    url = f"{BASE_URL}/products/{product_id}/candles"
    params = build_candles_params(window_start, window_end, granularity_seconds)

    for attempt in range(1, max_attempts + 1):
        is_last_attempt = attempt == max_attempts
        # Exponential backoff: wait 1s, then 2s, then 4s... (gives the server time to recover)
        wait_seconds = backoff_seconds * 2 ** (attempt - 1)

        try:
            response = get(url, params=params, headers=HEADERS, timeout=15)
        except (requests.ConnectionError, requests.Timeout):
            if is_last_attempt:
                raise
            sleep(wait_seconds)
            continue

        if response.status_code in RETRYABLE_STATUS and not is_last_attempt:
            sleep(wait_seconds)
            continue

        # Other errors (404, 400...) will not fix themselves: raise right away.
        # A 429/5xx on the last attempt also raises here.
        response.raise_for_status()
        return response.json()

    raise RuntimeError("unreachable: the loop always returns or raises")
