"""Split a long time range into windows that respect the API page limit."""
from datetime import datetime, timedelta

# Coinbase returns at most 300 candles per request (see ADR 0001)
MAX_CANDLES_PER_REQUEST = 300
ONE_HOUR_SECONDS = 3600


def split_into_windows(
    start: datetime,
    end: datetime,
    granularity_seconds: int = ONE_HOUR_SECONDS,
    max_candles: int = MAX_CANDLES_PER_REQUEST,
) -> list[tuple[datetime, datetime]]:
    """Return consecutive windows [window_start, window_end) covering [start, end).

    Each window holds at most `max_candles` candles. `start` is inclusive and
    `end` is exclusive. Both must be timezone-aware (we always work in UTC).
    """
    # Guard clause: a naive datetime has no timezone and causes silent bugs
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware (use UTC)")

    max_span = timedelta(seconds=granularity_seconds * max_candles)
    windows = []
    current = start
    while current < end:
        # The last window may be shorter, so never go past `end`
        window_end = min(current + max_span, end)
        windows.append((current, window_end))
        current = window_end  # next window starts exactly where this one ended
    return windows
