"""Transfers carry cost basis between accounts and never fabricate P&L."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def _setup(client, token):
    exchange = create_account(client, token, name="exchange", type="exchange")
    wallet = create_account(client, token, name="wallet", type="wallet")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    return exchange, wallet, irr, btc


def _realized(client, token):
    return client.get("/api/v1/reports/pnl", headers=auth_headers(token)).json()["realized"]


def _holding_qty(client, token, account_id, symbol):
    rows = client.get("/api/v1/holdings", headers=auth_headers(token)).json()
    for h in rows:
        if h["account_id"] == account_id and h["symbol"] == symbol:
            return Decimal(h["quantity"])
    return Decimal(0)


def test_transfer_carries_cost_no_pnl(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    exchange, wallet, irr, btc = _setup(client, token)
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": exchange, "asset_id": btc, "quantity": "1",
        "unit_price": "100", "price_currency": "IRR",
    })
    # transfer 1 BTC, no fee
    post_txn(client, token, {
        "type": "transfer", "occurred_at": "2026-01-02T00:00:00Z",
        "legs": [
            {"account_id": exchange, "asset_id": btc, "quantity": "-1"},
            {"account_id": wallet, "asset_id": btc, "quantity": "1"},
        ],
    })
    # no realized P&L from the transfer
    assert _realized(client, token)["irr"] is None
    assert _holding_qty(client, token, exchange, "BTC") == Decimal("0")
    assert _holding_qty(client, token, wallet, "BTC") == Decimal("1")

    # selling from the wallet uses the CARRIED cost (100), not market at transfer
    post_txn(client, token, {
        "type": "trade", "occurred_at": "2026-01-03T00:00:00Z",
        "legs": [
            {"account_id": wallet, "asset_id": btc, "quantity": "-1",
             "unit_price": "300", "price_currency": "IRR"},
            {"account_id": wallet, "asset_id": irr, "quantity": "300",
             "unit_price": "1", "price_currency": "IRR"},
        ],
    })
    assert Decimal(_realized(client, token)["irr"]) == Decimal("200")  # 300-100


def test_transfer_fee_raises_unit_cost(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    exchange, wallet, irr, btc = _setup(client, token)
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": exchange, "asset_id": btc, "quantity": "1",
        "unit_price": "100", "price_currency": "IRR",
    })
    # transfer with fee: send 1, receive 0.8, fee 0.2
    post_txn(client, token, {
        "type": "transfer", "occurred_at": "2026-01-02T00:00:00Z",
        "legs": [
            {"account_id": exchange, "asset_id": btc, "quantity": "-1"},
            {"account_id": wallet, "asset_id": btc, "quantity": "0.8"},
        ],
        "fee": "0.2", "fee_currency": "BTC",
    })
    assert _realized(client, token)["irr"] is None  # carry, no realized P&L
    assert _holding_qty(client, token, wallet, "BTC") == Decimal("0.8")

    # total carried cost 100 over 0.8 units -> unit cost 125; sell 0.8 @300
    post_txn(client, token, {
        "type": "trade", "occurred_at": "2026-01-03T00:00:00Z",
        "legs": [
            {"account_id": wallet, "asset_id": btc, "quantity": "-0.8",
             "unit_price": "300", "price_currency": "IRR"},
            {"account_id": wallet, "asset_id": irr, "quantity": "240",
             "unit_price": "1", "price_currency": "IRR"},
        ],
    })
    realized = _realized(client, token)
    # (300-125)*0.8 = 140 ; usd: (6 - 2.5)*0.8 = 2.8
    assert Decimal(realized["irr"]) == Decimal("140")
    assert Decimal(realized["usd"]) == Decimal("2.8")
