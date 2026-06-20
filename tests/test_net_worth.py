"""Net worth = assets - liabilities, in both IRR and USD."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import (
    add_liability_event,
    add_price,
    asset_id,
    auth_headers,
    create_account,
    create_liability,
    post_txn,
)


def _rebuild(client, token, day):
    return client.post(
        "/api/v1/snapshots/rebuild",
        json={"from": day, "to": day},
        headers=auth_headers(token),
    )


def _snapshot(client, token, day):
    rows = client.get(
        f"/api/v1/snapshots?from={day}&to={day}", headers=auth_headers(token)
    ).json()
    return rows[0]


def test_net_worth_assets_minus_liabilities(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")     # FX
    add_price(client, token, "BTC", "IRR", "400", "2026-01-01")
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "2",
        "unit_price": "100", "price_currency": "IRR",
    })
    lia = create_liability(client, token, currency="IRR")
    add_liability_event(client, token, lia["id"], type="disbursement",
                        amount="300", currency="IRR", occurred_at="2026-01-01T00:00:00Z")

    assert _rebuild(client, token, "2026-01-01").status_code == 201
    snap = _snapshot(client, token, "2026-01-01")
    # assets: 2*400 = 800 IRR (16 USD) ; liabilities 300 IRR (6 USD)
    assert Decimal(snap["total_assets_irr"]) == Decimal("800")
    assert Decimal(snap["total_assets_usd"]) == Decimal("16")
    assert Decimal(snap["total_liabilities_irr"]) == Decimal("300")
    assert Decimal(snap["total_liabilities_usd"]) == Decimal("6")
    assert Decimal(snap["net_worth_irr"]) == Decimal("500")
    assert Decimal(snap["net_worth_usd"]) == Decimal("10")


def test_usd_liability_converted_to_irr(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    lia = create_liability(client, token, currency="USD")
    add_liability_event(client, token, lia["id"], type="disbursement",
                        amount="4", currency="USD", occurred_at="2026-01-01T00:00:00Z")

    assert _rebuild(client, token, "2026-01-01").status_code == 201
    snap = _snapshot(client, token, "2026-01-01")
    # 4 USD outstanding -> 200 IRR
    assert Decimal(snap["total_liabilities_usd"]) == Decimal("4")
    assert Decimal(snap["total_liabilities_irr"]) == Decimal("200")
    assert Decimal(snap["net_worth_usd"]) == Decimal("-4")
    assert Decimal(snap["net_worth_irr"]) == Decimal("-200")
