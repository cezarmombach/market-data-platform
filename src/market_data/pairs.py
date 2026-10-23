"""Extract several pairs one at a time: a failure in one pair never stops the others."""
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from market_data.extract import (
    build_envelope,
    fetch_range,
    find_missing_candles,
    write_landing_file,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairResult:
    product_id: str
    candles: int = 0
    missing_hours: int = 0
    path: Path | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def extract_pair(
    product_id: str,
    start: datetime,
    end: datetime,
    base_dir: Path,
    ingested_at: datetime,
    fetch: Callable = fetch_range,
    sleep: Callable[[float], None] = time.sleep,
) -> PairResult:
    """Fetch one pair over [start, end) and save its raw JSON."""
    candles = fetch(product_id, start, end, sleep=sleep)
    missing = find_missing_candles(candles, start, end)
    envelope = build_envelope(product_id, start, end, candles, ingested_at)
    path = write_landing_file(base_dir, envelope)
    return PairResult(product_id, len(candles), len(missing), path)


def extract_pairs(
    product_ids: list[str],
    start: datetime,
    end: datetime,
    base_dir: Path,
    ingested_at: datetime,
    extract: Callable = extract_pair,
    sleep: Callable[[float], None] = time.sleep,
) -> list[PairResult]:
    """Extract each pair on its own and return one result per pair (ok or failed)."""
    results = []
    for product_id in product_ids:
        try:
            results.append(extract(product_id, start, end, base_dir, ingested_at, sleep=sleep))
        except Exception as error:  # isolate any failure to this pair
            # Keep the full traceback in the log, so a bug in our code can be located later
            logger.exception("extraction failed for %s", product_id)
            results.append(PairResult(product_id, error=f"{type(error).__name__}: {error}"))
    return results
