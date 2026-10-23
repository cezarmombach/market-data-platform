from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from market_data.pairs import PairResult, extract_pair, extract_pairs

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(hours=3)
NOW = datetime(2026, 10, 1, 3, 30, tzinfo=UTC)


def candle(hour):
    return [int((START + timedelta(hours=hour)).timestamp()), 1.0, 2.0, 1.5, 1.8, 10.0]


def test_extract_pair_saves_file_and_counts_missing(tmp_path):
    def fetch(product_id, start, end, sleep):
        return [candle(0), candle(2)]  # hour 1 is missing

    result = extract_pair("ETH-USD", START, END, tmp_path, NOW, fetch=fetch, sleep=lambda s: None)
    assert result.ok
    assert (result.candles, result.missing_hours) == (2, 1)
    assert result.path.exists()
    assert "ETH-USD" in result.path.parts


def test_one_failing_pair_does_not_stop_the_others():
    done = []

    def extract(product_id, start, end, base_dir, ingested_at, sleep):
        if product_id == "BAD-USD":
            raise requests.HTTPError("HTTP 404")
        done.append(product_id)
        return PairResult(product_id, candles=3, path=Path("x"))

    results = extract_pairs(
        ["A-USD", "BAD-USD", "B-USD"],
        START,
        END,
        Path("x"),
        NOW,
        extract=extract,
        sleep=lambda s: None,
    )
    assert done == ["A-USD", "B-USD"]
    assert [r.ok for r in results] == [True, False, True]
    assert results[1].product_id == "BAD-USD"
    assert results[1].error == "HTTPError: HTTP 404"


def test_all_pairs_succeed():
    def extract(product_id, start, end, base_dir, ingested_at, sleep):
        return PairResult(product_id, candles=3)

    results = extract_pairs(["A-USD"], START, END, Path("x"), NOW, extract=extract)
    assert all(r.ok for r in results)
