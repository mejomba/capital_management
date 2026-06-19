"""Holding the base currencies must surface cross-currency P&L:
USD held shows an IRR gain when the rial weakens; IRR held shows a USD loss."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, asset_id, auth_headers, create_account, post_txn


def _holding(client, token, symbol, as_of):
    rows = client.get(
        f"/api/v1/holdings?as_of={as_of}", headers=auth_headers(token)
    ).json()
    return next(h for h in rows if h["symbol"] == symbol)


def test_usd_holding_has_irr_gain_zero_usd(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    usd = asset_id(client, token, "USD")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "USD", "IRR", "60", "2026-02-01")  # rial weakens

    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": usd, "quantity": "100",
    })
    h = _holding(client, token, "USD", "2026-02-01T00:00:00Z")
    # cost: irr 50/usd, usd 1/usd. Now FX 60.
    assert Decimal(h["value_irr"]) == Decimal("6000")
    assert Decimal(h["unrealized_pnl_irr"]) == Decimal("1000")   # (60-50)*100
    assert Decimal(h["unrealized_pnl_usd"]) == Decimal("0")


def test_irr_holding_has_usd_loss_zero_irr(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "USD", "IRR", "60", "2026-02-01")

    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": irr, "quantity": "1000",
    })
    h = _holding(client, token, "IRR", "2026-02-01T00:00:00Z")
    # IRR cost in USD = 1/50; now worth 1/60 -> loss
    assert Decimal(h["unrealized_pnl_irr"]) == Decimal("0")
    assert Decimal(h["unrealized_pnl_usd"]) < 0
