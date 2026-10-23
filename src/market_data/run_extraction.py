"""Manual run: extract the last closed 48 hours of every verified USD pair, plus recent PTAX.

Run from the project root:  python -m market_data.run_extraction
Raw files go to data/landing (git-ignored).
"""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.extract import last_closed_hour_end
from market_data.pairs import extract_pairs
from market_data.products import CANDIDATE_PRODUCT_IDS, fetch_products, select_products
from market_data.ptax import build_ptax_envelope, fetch_ptax, write_ptax_file

HOURS = 48
PTAX_DAYS = 14
BASE_DIR = Path("data") / "landing"


def main() -> int:
    now = datetime.now(UTC)
    end = last_closed_hour_end(now)
    start = end - timedelta(hours=HOURS)

    usable, rejected = select_products(fetch_products(), CANDIDATE_PRODUCT_IDS)
    print(f"range: {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} UTC (end excluded)")
    print(f"verified pairs ({len(usable)}): {', '.join(usable)}")
    for product_id, reason in rejected.items():
        print(f"SKIPPED {product_id}: {reason}")

    results = extract_pairs(usable, start, end, BASE_DIR, ingested_at=now)
    for result in results:
        if result.ok:
            print(
                f"OK     {result.product_id}: {result.candles}/{HOURS} candles, "
                f"{result.missing_hours} missing"
            )
        else:
            print(f"FAILED {result.product_id}: {result.error}")

    failed = [result.product_id for result in results if not result.ok]
    ptax_failed = False
    try:
        # The API only returns bulletins that already exist, so asking up to today is safe
        ptax_end = now.date()
        ptax_start = ptax_end - timedelta(days=PTAX_DAYS)
        rows = fetch_ptax(ptax_start, ptax_end)
        path = write_ptax_file(BASE_DIR, build_ptax_envelope(ptax_start, ptax_end, rows, now))
        print(f"OK     PTAX: {len(rows)} bulletins -> {path}")
    except Exception as error:  # report it, do not hide the pair results
        ptax_failed = True
        print(f"FAILED PTAX: {type(error).__name__}: {error}")

    if failed:
        print(f"failed pairs: {', '.join(failed)}")
    return 1 if failed or ptax_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
