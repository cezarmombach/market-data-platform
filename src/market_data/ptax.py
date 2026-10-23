"""Client for the BCB PTAX closing bulletin (Olinda API, CotacaoDolarPeriodo)."""
import json
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import requests

from market_data.http import get_json_with_retry

URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)
DATE_FORMAT = "%m-%d-%Y"  # the API wants MM-DD-YYYY, not ISO
QUOTE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
REQUIRED_FIELDS = ("cotacaoCompra", "cotacaoVenda", "dataHoraCotacao")


class PtaxResponseError(ValueError):
    """The BCB response does not have the shape we expect."""


def build_ptax_params(start_date: date, end_date: date) -> dict:
    """Translate an inclusive date range into the Olinda query parameters."""
    # datetime is a subclass of date, but a time of day makes no sense for a daily bulletin
    if isinstance(start_date, datetime) or isinstance(end_date, datetime):
        raise ValueError("start_date and end_date must be dates, not datetimes")
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    return {
        "@dataInicial": f"'{start_date.strftime(DATE_FORMAT)}'",
        "@dataFinalCotacao": f"'{end_date.strftime(DATE_FORMAT)}'",
        "$format": "json",
    }


def validate_ptax_response(payload: object) -> list[dict]:
    """Check the response shape and return the rows (untouched).

    An empty list is valid: weekends and holidays have no bulletin.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise PtaxResponseError("expected a JSON object with a 'value' list")

    for index, row in enumerate(payload["value"]):
        if not isinstance(row, dict):
            raise PtaxResponseError(f"row {index} is not an object")
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise PtaxResponseError(f"row {index} is missing fields: {missing}")
        for field in ("cotacaoCompra", "cotacaoVenda"):
            value = row[field]
            # bool is an int subclass: reject it explicitly
            if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
                raise PtaxResponseError(f"row {index} has an invalid {field}: {value!r}")
        try:
            # Only a format check: the value is Brasilia time and is stored untouched
            datetime.strptime(row["dataHoraCotacao"], QUOTE_TIME_FORMAT)  # noqa: DTZ007
        except (TypeError, ValueError) as error:
            raise PtaxResponseError(
                f"row {index} has an invalid dataHoraCotacao: {row['dataHoraCotacao']!r}"
            ) from error
    return payload["value"]


def fetch_ptax(
    start_date: date,
    end_date: date,
    get: Callable = requests.get,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Fetch the closing PTAX rows of [start_date, end_date] (inclusive), validated."""
    params = build_ptax_params(start_date, end_date)
    payload = get_json_with_retry(URL, params, get=get, sleep=sleep)
    return validate_ptax_response(payload)


def build_ptax_envelope(
    start_date: date, end_date: date, rows: list[dict], ingested_at: datetime
) -> dict:
    """Wrap the untouched API rows with metadata (the raw data itself is not changed)."""
    if ingested_at.tzinfo is None:
        raise ValueError("ingested_at must be timezone-aware (use UTC)")
    return {
        "source": "bcb_ptax",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ingested_at": ingested_at.isoformat(),
        # dataHoraCotacao has no timezone in the API: it is Brasilia time
        "quote_time_zone": "America/Sao_Paulo",
        "rows": rows,
    }


def write_ptax_file(base_dir: Path, envelope: dict) -> Path:
    """Write the envelope as JSON and return the file path."""
    start = date.fromisoformat(envelope["start_date"])
    end = date.fromisoformat(envelope["end_date"])
    folder = base_dir / "bcb_ptax"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"ptax_{start:%Y%m%d}_{end:%Y%m%d}.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    return path
