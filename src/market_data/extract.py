"""Extraction helpers: fetch a long range of candles, check it and save it as raw JSON."""
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.coinbase import fetch_candles_window
from market_data.windows import split_into_windows

ONE_HOUR = timedelta(hours=1)
PAUSE_BETWEEN_CALLS_SECONDS = 0.2  # keeps us far below 10 requests per second


def last_closed_hour_end(now: datetime) -> datetime:
    """Return the start of the current hour: every candle before it is closed.

    Used as the exclusive end of the range, so the open (partial) candle is never loaded.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (use UTC)")
    return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def fetch_range(
    product_id: str,
    start: datetime,
    end: datetime,
    fetch_window: Callable = fetch_candles_window,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list]:
    """Fetch all hourly candles in [start, end): one call per window, deduplicated, ascending."""
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    by_timestamp: dict[int, list] = {}

    for window_start, window_end in split_into_windows(start, end):
        for candle in fetch_window(product_id, window_start, window_end):
            timestamp = candle[0]
            # The API may return candles outside the asked range (see the docs): drop them
            if start_ts <= timestamp < end_ts:
                by_timestamp[timestamp] = candle  # same timestamp twice keeps one row
        sleep(PAUSE_BETWEEN_CALLS_SECONDS)

    return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]


def find_missing_candles(candles: list[list], start: datetime, end: datetime) -> list[datetime]:
    """Return the hours in [start, end) that have no candle."""
    present = {candle[0] for candle in candles}
    missing = []
    current = start
    while current < end:
        if int(current.timestamp()) not in present:
            missing.append(current)
        current += ONE_HOUR
    return missing


def build_envelope(
    product_id: str,
    start: datetime,
    end: datetime,
    candles: list[list],
    ingested_at: datetime,
) -> dict:
    """Wrap the untouched API rows with metadata (the raw data itself is not changed)."""
    return {
        "source": "coinbase_exchange",
        "product_id": product_id,
        "granularity_seconds": 3600,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "ingested_at": ingested_at.isoformat(),
        "candle_columns": ["time", "low", "high", "open", "close", "volume"],
        "candles": candles,
    }


def write_landing_file(base_dir: Path, envelope: dict) -> Path:
    """Write the envelope as JSON and return the file path."""
    start = datetime.fromisoformat(envelope["window_start"])
    end = datetime.fromisoformat(envelope["window_end"])
    # No colons in the name: Windows does not allow them in file names
    name = f"candles_{start:%Y%m%dT%H%M%SZ}_{end:%Y%m%dT%H%M%SZ}.json"
    folder = base_dir / "coinbase" / envelope["product_id"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(envelope), encoding="utf-8")
    return path
