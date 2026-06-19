from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers


def test_create_and_list_price(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    add_price(client, token, "BTC", "IRR", "100", "2026-01-01")
    resp = client.get("/api/v1/prices?page_size=50", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["price"] == "100.000000000000000000"
    assert body["items"][0]["source"] == "manual"


def test_list_filters_by_asset_and_date(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    add_price(client, token, "BTC", "IRR", "100", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "200", "2026-02-01")
    add_price(client, token, "ETH", "IRR", "50", "2026-01-01")
    btc = asset_id(client, token, "BTC")
    resp = client.get(
        f"/api/v1/prices?asset_id={btc}&from=2026-01-15&to=2026-03-01",
        headers=auth_headers(token),
    )
    rows = resp.json()["items"]
    assert len(rows) == 1
    assert rows[0]["price"] == "200.000000000000000000"


def test_bulk_prices(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    btc = asset_id(client, token, "BTC")
    resp = client.post(
        "/api/v1/prices/bulk",
        json=[
            {"asset_id": btc, "quote_currency": "IRR", "price": "100", "as_of": "2026-01-01"},
            {"asset_id": btc, "quote_currency": "IRR", "price": "150", "as_of": "2026-01-02"},
        ],
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()) == 2


def test_fx_nearest_as_of(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "USD", "IRR", "60", "2026-02-01")

    r1 = client.get("/api/v1/fx?from=USD&to=IRR&as_of=2026-01-15", headers=auth_headers(token))
    assert Decimal(r1.json()["rate"]) == Decimal("50")

    r2 = client.get("/api/v1/fx?from=USD&to=IRR&as_of=2026-02-15", headers=auth_headers(token))
    assert Decimal(r2.json()["rate"]) == Decimal("60")

    # inverse direction
    r3 = client.get("/api/v1/fx?from=IRR&to=USD&as_of=2026-01-15", headers=auth_headers(token))
    assert Decimal(r3.json()["rate"]) == Decimal(1) / Decimal("50")


def test_fx_missing_returns_null(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    resp = client.get("/api/v1/fx?from=USD&to=IRR&as_of=2026-01-01", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["rate"] is None


def test_prices_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/prices").status_code == 401
