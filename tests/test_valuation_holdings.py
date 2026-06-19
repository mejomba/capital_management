from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def test_holding_unvalued_when_no_price(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    # deposit with no cost basis and no prices at all
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
    })
    h = next(
        x for x in client.get("/api/v1/holdings", headers=auth_headers(token)).json()
        if x["symbol"] == "BTC"
    )
    assert Decimal(h["quantity"]) == Decimal("1")
    assert h["value_irr"] is None
    assert h["unrealized_pnl_irr"] is None


def test_holding_value_and_unrealized(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "2",
        "unit_price": "100", "price_currency": "IRR",
    })
    add_price(client, token, "BTC", "IRR", "400", "2026-01-02")

    h = next(
        x for x in client.get(
            "/api/v1/holdings?as_of=2026-01-02T00:00:00Z", headers=auth_headers(token)
        ).json()
        if x["symbol"] == "BTC"
    )
    assert Decimal(h["value_irr"]) == Decimal("800")          # 2 * 400
    assert Decimal(h["value_usd"]) == Decimal("16")           # 800 / 50
    assert Decimal(h["unrealized_pnl_irr"]) == Decimal("600")  # (400-100)*2
    assert Decimal(h["unrealized_pnl_usd"]) == Decimal("12")   # (8-2)*2


def test_by_asset_and_by_class_valued(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    a1 = create_account(client, token, name="a1", type="exchange")
    a2 = create_account(client, token, name="a2", type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    for acc in (a1, a2):
        post_txn(client, token, {
            "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
            "account_id": acc, "asset_id": btc, "quantity": "1",
            "unit_price": "100", "price_currency": "IRR",
        })
    add_price(client, token, "BTC", "IRR", "400", "2026-01-02")

    by_asset = client.get(
        "/api/v1/holdings/by-asset?as_of=2026-01-02T00:00:00Z",
        headers=auth_headers(token),
    ).json()
    row = next(r for r in by_asset if r["symbol"] == "BTC")
    assert Decimal(row["quantity"]) == Decimal("2")
    assert Decimal(row["value_irr"]) == Decimal("800")
    assert Decimal(row["unrealized_pnl_irr"]) == Decimal("600")

    by_class = client.get(
        "/api/v1/holdings/by-class?as_of=2026-01-02T00:00:00Z",
        headers=auth_headers(token),
    ).json()
    crypto = next(c for c in by_class if c["asset_class"] == "crypto")
    assert Decimal(crypto["items"][0]["value_irr"]) == Decimal("800")
