"""Shared HTTP helper: GET a JSON endpoint, retrying temporary failures."""
import time
from collections.abc import Callable

import requests

HEADERS = {"User-Agent": "market-data-platform/0.1"}
# Temporary problems worth retrying: rate limit (429) and server errors (5xx)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def get_json_with_retry(
    url: str,
    params: dict | None = None,
    max_attempts: int = 4,
    backoff_seconds: float = 1.0,
    get: Callable = requests.get,
    sleep: Callable[[float], None] = time.sleep,
):
    """GET `url` and return the decoded JSON, retrying temporary failures.

    `get` and `sleep` can be replaced in tests, so no real network or waiting is needed.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

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
