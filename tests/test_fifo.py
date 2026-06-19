"""Multi-lot FIFO, partial sells, and dual-currency realized P&L."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def _setup(client: TestClient, token: str) -> tuple[str, str, str]:
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")  # FX
    return acc, irr, btc


def _deposit_btc(client, token, acc, btc, qty, cost, when):
    return post_txn(client, token, {
        "type": "deposit", "occurred_at": when,
        "account_id": acc, "asset_id": btc, "quantity": qty,
        "unit_price": cost, "price_currency": "IRR",
    })


def _sell_btc(client, token, acc, btc, irr, qty, price, when):
    total = str(Decimal(qty) * Decimal(price))
    return post_txn(client, token, {
        "type": "trade", "occurred_at": when,
        "legs": [
            {"account_id": acc, "asset_id": btc, "quantity": f"-{qty}",
             "unit_price": price, "price_currency": "IRR"},
            {"account_id": acc, "asset_id": irr, "quantity": total,
             "unit_price": "1", "price_currency": "IRR"},
        ],
    })


def _realized(client, token):
    return client.get("/api/v1/reports/pnl", headers=auth_headers(token)).json()["realized"]


def test_multi_lot_partial_sell_realized_dual_currency(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    _deposit_btc(client, token, acc, btc, "1", "100", "2026-01-01")   # lot1: irr 100, usd 2
    _deposit_btc(client, token, acc, btc, "1", "200", "2026-01-02")   # lot2: irr 200, usd 4
    r = _sell_btc(client, token, acc, btc, irr, "1.5", "300", "2026-01-03")
    assert r.status_code == 201, r.text

    # FIFO: lot1 fully (1) + lot2 half (0.5)
    # realized irr = (300-100)*1 + (300-200)*0.5 = 250 ; usd = (6-2)*1 + (6-4)*0.5 = 5
    realized = _realized(client, token)
    assert Decimal(realized["irr"]) == Decimal("250")
    assert Decimal(realized["usd"]) == Decimal("5")

    # remaining BTC holding = 0.5
    holdings = client.get("/api/v1/holdings", headers=auth_headers(token)).json()
    btc_row = next(h for h in holdings if h["symbol"] == "BTC")
    assert Decimal(btc_row["quantity"]) == Decimal("0.5")


def test_sell_spanning_multiple_lots(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    _deposit_btc(client, token, acc, btc, "1", "100", "2026-01-01")
    _deposit_btc(client, token, acc, btc, "1", "200", "2026-01-02")
    _deposit_btc(client, token, acc, btc, "1", "300", "2026-01-03")
    # sell 2.5 -> lot1(1)+lot2(1)+lot3(0.5) at 400
    _sell_btc(client, token, acc, btc, irr, "2.5", "400", "2026-01-04")
    # irr = (400-100)+(400-200)+(400-300)*0.5 = 300+200+50 = 550
    realized = _realized(client, token)
    assert Decimal(realized["irr"]) == Decimal("550")


def test_oversell_rejected_keeps_lots(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    _deposit_btc(client, token, acc, btc, "1", "100", "2026-01-01")
    r = _sell_btc(client, token, acc, btc, irr, "2", "300", "2026-01-02")
    assert r.status_code == 422
    realized = _realized(client, token)
    assert realized["irr"] is None  # nothing realized
