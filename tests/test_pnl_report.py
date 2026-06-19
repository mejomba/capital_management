from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def _setup(client, token):
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    return acc, irr, btc


def test_pnl_realized_and_unrealized_grouped(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "2",
        "unit_price": "100", "price_currency": "IRR",
    })
    # sell 1 BTC @300 -> realized irr (300-100)*1 = 200
    post_txn(client, token, {
        "type": "trade", "occurred_at": "2026-01-02T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": btc, "quantity": "-1",
             "unit_price": "300", "price_currency": "IRR"},
            {"account_id": acc, "asset_id": irr, "quantity": "300",
             "unit_price": "1", "price_currency": "IRR"},
        ],
    })
    add_price(client, token, "BTC", "IRR", "400", "2026-01-03")

    report = client.get(
        "/api/v1/reports/pnl?to=2026-01-03&group_by=asset",
        headers=auth_headers(token),
    ).json()
    assert Decimal(report["realized"]["irr"]) == Decimal("200")
    # unrealized: remaining 1 BTC at 400 vs cost 100 = 300 ; plus IRR proceeds lot (0)
    btc_group = next(g for g in report["groups"] if g["key"] == "BTC")
    assert Decimal(btc_group["realized_irr"]) == Decimal("200")
    assert Decimal(btc_group["unrealized_irr"]) == Decimal("300")


def test_pnl_realized_filtered_by_date(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "2",
        "unit_price": "100", "price_currency": "IRR",
    })
    post_txn(client, token, {
        "type": "trade", "occurred_at": "2026-03-01T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": btc, "quantity": "-1",
             "unit_price": "300", "price_currency": "IRR"},
            {"account_id": acc, "asset_id": irr, "quantity": "300",
             "unit_price": "1", "price_currency": "IRR"},
        ],
    })
    # window excludes the March sale
    report = client.get(
        "/api/v1/reports/pnl?from=2026-01-01&to=2026-02-01",
        headers=auth_headers(token),
    ).json()
    assert report["realized"]["irr"] is None


def test_pnl_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/pnl").status_code == 401
