import json
from datetime import UTC, datetime, timedelta

import pytest

from market_data.extract import (
    build_envelope,
    fetch_range,
    find_missing_candles,
    last_closed_hour_end,
    write_landing_file,
)

START = datetime(2026, 10, 1, tzinfo=UTC)


def hours(n: int) -> timedelta:
    return timedelta(hours=n)


def candle(hour_offset: int) -> list:
    """Fake raw Coinbase row for the candle that starts `hour_offset` hours after START."""
    return [int((START + hours(hour_offset)).timestamp()), 1.0, 2.0, 1.5, 1.8, 10.0]


def fake_fetch_window(product_id, window_start, window_end):
    """Fake API: descending order, one repeated edge candle and one candle before the start."""
    first = int((window_start - START) / hours(1))
    last = int((window_end - START) / hours(1)) - 1
    rows = [candle(h) for h in range(last, first - 1, -1)]  # newest first, like Coinbase
    rows.append(candle(first))  # duplicate row
    rows.append(candle(first - 1))  # candle before the asked start
    return rows


def test_last_closed_hour_end_floors_to_the_hour():
    now = datetime(2026, 10, 22, 17, 47, 12, 345, tzinfo=UTC)
    assert last_closed_hour_end(now) == datetime(2026, 10, 22, 17, 0, tzinfo=UTC)


def test_last_closed_hour_end_on_exact_hour_stays_there():
    now = datetime(2026, 10, 22, 17, 0, tzinfo=UTC)
    assert last_closed_hour_end(now) == now


def test_last_closed_hour_end_rejects_naive_datetime():
    with pytest.raises(ValueError):
        last_closed_hour_end(datetime(2026, 10, 22, 17, 47))


def test_fetch_range_over_three_windows_returns_sorted_unique_rows():
    end = START + hours(720)
    rows = fetch_range("BTC-USD", START, end, fetch_window=fake_fetch_window, sleep=lambda s: None)
    timestamps = [row[0] for row in rows]
    assert len(rows) == 720
    assert timestamps == sorted(set(timestamps))
    assert timestamps[0] == int(START.timestamp())
    assert timestamps[-1] == int((end - hours(1)).timestamp())


def test_fetch_range_pauses_once_per_window():
    sleeps = []
    fetch_range(
        "BTC-USD", START, START + hours(720), fetch_window=fake_fetch_window, sleep=sleeps.append
    )
    assert len(sleeps) == 3


def test_find_missing_candles_reports_the_gap():
    candles = [candle(0), candle(1), candle(3)]
    assert find_missing_candles(candles, START, START + hours(4)) == [START + hours(2)]


def test_find_missing_candles_is_empty_when_complete():
    candles = [candle(h) for h in range(4)]
    assert find_missing_candles(candles, START, START + hours(4)) == []


def test_envelope_keeps_the_raw_rows_untouched():
    rows = [candle(0), candle(1)]
    ingested_at = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)
    envelope = build_envelope("BTC-USD", START, START + hours(2), rows, ingested_at)
    assert envelope["candles"] == rows
    assert envelope["product_id"] == "BTC-USD"
    assert envelope["ingested_at"] == "2026-10-22T18:00:00+00:00"


def test_write_landing_file_creates_a_readable_json(tmp_path):
    rows = [candle(0)]
    envelope = build_envelope("BTC-USD", START, START + hours(1), rows, START)
    path = write_landing_file(tmp_path, envelope)
    assert path.name == "candles_20261001T000000Z_20261001T010000Z.json"
    assert path.parent == tmp_path / "coinbase" / "BTC-USD"
    assert json.loads(path.read_text(encoding="utf-8")) == envelope
