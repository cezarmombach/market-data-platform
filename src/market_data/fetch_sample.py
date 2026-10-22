"""Manual run: fetch the last closed 48 hours of BTC-USD and save the raw JSON locally.

Run from the project root:  python -m market_data.fetch_sample
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.extract import (
    build_envelope,
    fetch_range,
    find_missing_candles,
    last_closed_hour_end,
    write_landing_file,
)

PRODUCT_ID = "BTC-USD"
HOURS = 48
BASE_DIR = Path("data") / "landing"


def main() -> None:
    now = datetime.now(UTC)
    end = last_closed_hour_end(now)
    start = end - timedelta(hours=HOURS)

    candles = fetch_range(PRODUCT_ID, start, end)
    missing = find_missing_candles(candles, start, end)
    envelope = build_envelope(PRODUCT_ID, start, end, candles, ingested_at=now)
    path = write_landing_file(BASE_DIR, envelope)

    print(f"range:    {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} UTC (end excluded)")
    print(f"expected: {HOURS} candles | received: {len(candles)} | missing: {len(missing)}")
    if candles:
        print(f"first candle: {datetime.fromtimestamp(candles[0][0], UTC):%Y-%m-%d %H:%M} UTC")
        print(f"last candle:  {datetime.fromtimestamp(candles[-1][0], UTC):%Y-%m-%d %H:%M} UTC")
        print(f"sample row:   {candles[-1]}")
    for hour in missing[:10]:
        print(f"missing hour: {hour:%Y-%m-%d %H:%M} UTC")
    print(f"saved: {path}")


if __name__ == "__main__":
    main()
