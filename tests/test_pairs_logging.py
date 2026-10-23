import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.pairs import extract_pairs

START = datetime(2026, 10, 1, tzinfo=UTC)
END = START + timedelta(hours=3)


class ListHandler(logging.Handler):
    """Collect log records in a list, so the test can inspect them."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def failing_extract(product_id, start, end, base_dir, ingested_at, sleep=None):
    raise TypeError("bug inside our code")


def test_a_failing_pair_is_logged_with_its_traceback():
    handler = ListHandler()
    logger = logging.getLogger("market_data.pairs")
    logger.addHandler(handler)
    try:
        results = extract_pairs(
            ["BTC-USD"], START, END, Path("unused"), START, extract=failing_extract
        )
    finally:
        logger.removeHandler(handler)

    assert results[0].error == "TypeError: bug inside our code"
    assert len(handler.records) == 1
    assert handler.records[0].exc_info is not None  # the traceback was kept
    assert "BTC-USD" in handler.records[0].getMessage()
