"""Client for the Coinbase Exchange public candles endpoint (one window per call)."""
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests

from market_data.http import get_json_with_retry

BASE_URL = "https://api.exchange.coinbase.com"
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
    """Fetch the raw candles of one window, retrying temporary failures (see http.py)."""
    url = f"{BASE_URL}/products/{product_id}/candles"
    params = build_candles_params(window_start, window_end, granularity_seconds)
    return get_json_with_retry(
        url,
        params,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        get=get,
        sleep=sleep,
    )
