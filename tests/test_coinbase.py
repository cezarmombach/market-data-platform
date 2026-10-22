from datetime import UTC, datetime, timedelta

import pytest
import requests

from market_data.coinbase import build_candles_params, fetch_candles_window

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(hours=3)
CANDLES = [[1792000000, 1.0, 2.0, 1.5, 1.8, 10.0]]


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def scripted_get(outcomes):
    """Build a fake `get` that returns (or raises) the given outcomes in order."""
    calls = []
    remaining = list(outcomes)

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return get, calls


def test_params_use_the_last_candle_as_inclusive_end():
    params = build_candles_params(START, END)
    assert params == {
        "granularity": 3600,
        "start": "2026-10-01T00:00:00Z",
        "end": "2026-10-01T02:00:00Z",
    }


def test_params_reject_naive_datetimes():
    with pytest.raises(ValueError):
        build_candles_params(datetime(2026, 10, 1), datetime(2026, 10, 1, 3))


def test_params_reject_empty_window():
    with pytest.raises(ValueError):
        build_candles_params(START, START)


def test_returns_candles_on_first_success():
    get, calls = scripted_get([FakeResponse(200, CANDLES)])
    result = fetch_candles_window("BTC-USD", START, END, get=get, sleep=lambda s: None)
    assert result == CANDLES
    assert len(calls) == 1
    assert calls[0][0].endswith("/products/BTC-USD/candles")


def test_retries_after_a_server_error_and_then_succeeds():
    get, calls = scripted_get([FakeResponse(503), FakeResponse(200, CANDLES)])
    sleeps = []
    result = fetch_candles_window("BTC-USD", START, END, get=get, sleep=sleeps.append)
    assert result == CANDLES
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_backoff_doubles_between_attempts():
    get, _ = scripted_get([FakeResponse(503), FakeResponse(429), FakeResponse(200, CANDLES)])
    sleeps = []
    fetch_candles_window("BTC-USD", START, END, get=get, sleep=sleeps.append)
    assert sleeps == [1.0, 2.0]


def test_retries_after_a_connection_error():
    get, calls = scripted_get([requests.ConnectionError("boom"), FakeResponse(200, CANDLES)])
    result = fetch_candles_window("BTC-USD", START, END, get=get, sleep=lambda s: None)
    assert result == CANDLES
    assert len(calls) == 2


def test_gives_up_after_max_attempts():
    get, calls = scripted_get([FakeResponse(503)] * 4)
    sleeps = []
    with pytest.raises(requests.HTTPError):
        fetch_candles_window("BTC-USD", START, END, get=get, sleep=sleeps.append)
    assert len(calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_does_not_retry_client_errors():
    get, calls = scripted_get([FakeResponse(404)])
    with pytest.raises(requests.HTTPError):
        fetch_candles_window("NOPE-USD", START, END, get=get, sleep=lambda s: None)
    assert len(calls) == 1
