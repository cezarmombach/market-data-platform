import pytest

from market_data.products import fetch_products, select_products


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def product(product_id, quote="USD", status="online", disabled=False):
    return {
        "id": product_id,
        "quote_currency": quote,
        "status": status,
        "trading_disabled": disabled,
    }


def test_select_keeps_usable_ids_in_wanted_order():
    products = [product("ETH-USD"), product("BTC-USD")]
    usable, rejected = select_products(products, ["BTC-USD", "ETH-USD"])
    assert usable == ["BTC-USD", "ETH-USD"]
    assert rejected == {}


def test_select_reports_why_each_id_is_rejected():
    products = [
        product("OLD-USD", status="delisted"),
        product("OFF-USD", disabled=True),
        product("BTC-EUR", quote="EUR"),
        product("BTC-USD"),
    ]
    usable, rejected = select_products(
        products, ["BTC-USD", "NOPE-USD", "OLD-USD", "OFF-USD", "BTC-EUR"]
    )
    assert usable == ["BTC-USD"]
    assert set(rejected) == {"NOPE-USD", "OLD-USD", "OFF-USD", "BTC-EUR"}
    assert "not listed" in rejected["NOPE-USD"]
    assert "delisted" in rejected["OLD-USD"]
    assert "disabled" in rejected["OFF-USD"]
    assert "EUR" in rejected["BTC-EUR"]


def test_select_ignores_duplicate_wanted_ids():
    usable, _ = select_products([product("BTC-USD")], ["BTC-USD", "BTC-USD"])
    assert usable == ["BTC-USD"]


def test_fetch_products_returns_list():
    def get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/products")
        return FakeResponse([product("BTC-USD")])

    assert fetch_products(get=get, sleep=lambda s: None) == [product("BTC-USD")]


def test_fetch_products_rejects_unexpected_shape():
    def get(url, params=None, headers=None, timeout=None):
        return FakeResponse({"message": "oops"})

    with pytest.raises(ValueError):
        fetch_products(get=get, sleep=lambda s: None)
