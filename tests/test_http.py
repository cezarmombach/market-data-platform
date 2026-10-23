import pytest
import requests

from market_data.http import get_json_with_retry


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def scripted_get(outcomes):
    remaining = list(outcomes)

    def get(url, params=None, headers=None, timeout=None):
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return get


def test_returns_json_on_success():
    get = scripted_get([FakeResponse(200, {"ok": True})])
    assert get_json_with_retry("http://x", get=get, sleep=lambda s: None) == {"ok": True}


def test_retries_503_then_succeeds_with_backoff():
    sleeps = []
    get = scripted_get([FakeResponse(503), FakeResponse(429), FakeResponse(200, [1])])
    assert get_json_with_retry("http://x", get=get, sleep=sleeps.append) == [1]
    assert sleeps == [1.0, 2.0]


def test_does_not_retry_404():
    sleeps = []
    get = scripted_get([FakeResponse(404)])
    with pytest.raises(requests.HTTPError):
        get_json_with_retry("http://x", get=get, sleep=sleeps.append)
    assert sleeps == []


def test_raises_connection_error_after_last_attempt():
    get = scripted_get([requests.ConnectionError()] * 2)
    with pytest.raises(requests.ConnectionError):
        get_json_with_retry("http://x", max_attempts=2, get=get, sleep=lambda s: None)


def test_rejects_zero_attempts():
    with pytest.raises(ValueError):
        get_json_with_retry("http://x", max_attempts=0)
