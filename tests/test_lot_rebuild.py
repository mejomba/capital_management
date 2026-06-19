"""Lots are a projection: changing active history rebuilds them from scratch."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def _setup(client, token):
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    return acc, irr, btc


def _deposit(client, token, acc, btc, qty, cost, when):
    post_txn(client, token, {
        "type": "deposit", "occurred_at": when,
        "account_id": acc, "asset_id": btc, "quantity": qty,
        "unit_price": cost, "price_currency": "IRR",
    })


def _sell(client, token, acc, btc, irr, qty, price, when):
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


def _btc_qty(client, token):
    rows = client.get("/api/v1/holdings", headers=auth_headers(token)).json()
    return sum((Decimal(h["quantity"]) for h in rows if h["symbol"] == "BTC"), Decimal(0))


def test_reverse_sell_rebuilds_lots(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    _deposit(client, token, acc, btc, "1", "100", "2026-01-01")  # lot A
    _deposit(client, token, acc, btc, "1", "200", "2026-01-02")  # lot B
    sell = _sell(client, token, acc, btc, irr, "1", "300", "2026-01-03").json()
    assert Decimal(_realized(client, token)["irr"]) == Decimal("200")  # consumed lot A
    assert _btc_qty(client, token) == Decimal("1")

    # reverse the sell -> lots A and B restored, realized gone, holding back to 2
    r = client.post(
        f"/api/v1/transactions/{sell['id']}/reverse", headers=auth_headers(token)
    )
    assert r.status_code == 201, r.text
    assert _realized(client, token)["irr"] is None
    assert _btc_qty(client, token) == Decimal("2")

    # FIFO order preserved: a fresh sell again consumes lot A first (cost 100)
    _sell(client, token, acc, btc, irr, "1", "500", "2026-01-04")
    assert Decimal(_realized(client, token)["irr"]) == Decimal("400")  # 500-100


def test_reverse_buy_midhistory_rebuilds(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc, irr, btc = _setup(client, token)
    _deposit(client, token, acc, btc, "1", "100", "2026-01-01")  # lot A
    # capture lot B's transaction id
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-02T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
        "unit_price": "200", "price_currency": "IRR",
    })
    txns = client.get("/api/v1/transactions", headers=auth_headers(token)).json()["items"]
    lot_b = next(t for t in txns if t["legs"][0]["quantity"].startswith("1")
                 and t["occurred_at"].startswith("2026-01-02"))

    _sell(client, token, acc, btc, irr, "0.5", "300", "2026-01-03")  # consumes lot A 0.5
    assert Decimal(_realized(client, token)["irr"]) == Decimal("100")  # (300-100)*0.5

    # reverse the (unsold) lot B buy -> holding drops by 1, realized unchanged
    r = client.post(
        f"/api/v1/transactions/{lot_b['id']}/reverse", headers=auth_headers(token)
    )
    assert r.status_code == 201, r.text
    assert _btc_qty(client, token) == Decimal("0.5")
    assert Decimal(_realized(client, token)["irr"]) == Decimal("100")
