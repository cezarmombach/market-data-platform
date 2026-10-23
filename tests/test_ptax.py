import json
from datetime import UTC, date, datetime

import pytest

from market_data.ptax import (
    PtaxResponseError,
    build_ptax_envelope,
    build_ptax_params,
    fetch_ptax,
    validate_ptax_response,
    write_ptax_file,
)

ROW = {
    "cotacaoCompra": 5.0558,
    "cotacaoVenda": 5.0564,
    "dataHoraCotacao": "2026-10-19 13:05:47.20983",
}


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def test_params_use_month_day_year():
    params = build_ptax_params(date(2026, 10, 1), date(2026, 10, 22))
    assert params["@dataInicial"] == "'10-01-2026'"
    assert params["@dataFinalCotacao"] == "'10-22-2026'"
    assert params["$format"] == "json"


def test_params_reject_reversed_range():
    with pytest.raises(ValueError):
        build_ptax_params(date(2026, 10, 22), date(2026, 10, 1))


def test_params_reject_datetimes():
    with pytest.raises(ValueError):
        build_ptax_params(datetime(2026, 10, 1, tzinfo=UTC), date(2026, 10, 2))


def test_validate_returns_rows_untouched():
    assert validate_ptax_response({"value": [ROW]}) == [ROW]


def test_validate_accepts_empty_value_for_weekends():
    assert validate_ptax_response({"value": []}) == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"value": "x"},
        {"value": [1]},
        {"value": [{"cotacaoCompra": 5.0}]},
        {"value": [{**ROW, "cotacaoCompra": "5.05"}]},
        {"value": [{**ROW, "cotacaoVenda": 0}]},
        {"value": [{**ROW, "cotacaoVenda": True}]},
        {"value": [{**ROW, "dataHoraCotacao": "19/10/2026"}]},
        {"value": [{**ROW, "dataHoraCotacao": None}]},
    ],
)
def test_validate_rejects_bad_shapes(payload):
    with pytest.raises(PtaxResponseError):
        validate_ptax_response(payload)


def test_fetch_ptax_calls_api_and_validates():
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        return FakeResponse({"value": [ROW]})

    rows = fetch_ptax(date(2026, 10, 19), date(2026, 10, 19), get=get, sleep=lambda s: None)
    assert rows == [ROW]
    assert "CotacaoDolarPeriodo" in calls[0][0]
    assert calls[0][1]["@dataInicial"] == "'10-19-2026'"


def test_fetch_ptax_rejects_invalid_response():
    def get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"error": "x"})

    with pytest.raises(PtaxResponseError):
        fetch_ptax(date(2026, 10, 19), date(2026, 10, 19), get=get, sleep=lambda s: None)


def test_envelope_keeps_rows_and_marks_time_zone():
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    envelope = build_ptax_envelope(date(2026, 10, 19), date(2026, 10, 22), [ROW], now)
    assert envelope["rows"] == [ROW]
    assert envelope["quote_time_zone"] == "America/Sao_Paulo"
    assert envelope["ingested_at"] == "2026-10-23T12:00:00+00:00"


def test_envelope_rejects_naive_ingested_at():
    with pytest.raises(ValueError):
        build_ptax_envelope(date(2026, 10, 19), date(2026, 10, 22), [], datetime(2026, 10, 23))


def test_write_ptax_file(tmp_path):
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    envelope = build_ptax_envelope(date(2026, 10, 19), date(2026, 10, 22), [ROW], now)
    path = write_ptax_file(tmp_path, envelope)
    assert path == tmp_path / "bcb_ptax" / "ptax_20261019_20261022.json"
    assert json.loads(path.read_text(encoding="utf-8")) == envelope
