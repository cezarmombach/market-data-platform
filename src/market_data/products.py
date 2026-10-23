"""Check which Coinbase products we want to extract really exist (never assume the list)."""
import time
from collections.abc import Callable

import requests

from market_data.coinbase import BASE_URL
from market_data.http import get_json_with_retry

# Large, long-lived USD pairs. This is only a wish list: every id is checked against the API.
CANDIDATE_PRODUCT_IDS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "XRP-USD",
    "ADA-USD",
    "DOGE-USD",
    "LTC-USD",
    "LINK-USD",
    "AVAX-USD",
    "DOT-USD",
]


def fetch_products(
    get: Callable = requests.get,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Fetch the raw list of products from GET /products."""
    payload = get_json_with_retry(f"{BASE_URL}/products", get=get, sleep=sleep)
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("expected /products to return a list of objects")
    return payload


def select_products(
    products: list[dict], wanted_ids: list[str]
) -> tuple[list[str], dict[str, str]]:
    """Split the wanted ids into (usable ids, {unusable id: reason}).

    Usable means: listed, quoted in USD, status online and trading not disabled.
    The order of `wanted_ids` is kept.
    """
    by_id = {product.get("id"): product for product in products}
    usable: list[str] = []
    rejected: dict[str, str] = {}

    for product_id in dict.fromkeys(wanted_ids):  # drops duplicates, keeps order
        product = by_id.get(product_id)
        if product is None:
            rejected[product_id] = "not listed in /products"
        elif product.get("quote_currency") != "USD":
            rejected[product_id] = f"quote currency is {product.get('quote_currency')!r}, not USD"
        elif product.get("status") != "online":
            rejected[product_id] = f"status is {product.get('status')!r}, not 'online'"
        elif product.get("trading_disabled"):
            rejected[product_id] = "trading is disabled"
        else:
            usable.append(product_id)
    return usable, rejected
