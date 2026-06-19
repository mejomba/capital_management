"""Reconciliation invariants (must stay green per CLAUDE.md §12)."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import asset_id, auth_headers, create_account


def _post(client, token, body):
    return client.post("/api/v1/transactions", json=body, headers=auth_headers(token))


def _holding(client, token, account_id, symbol) -> Decimal:
    rows = client.get("/api/v1/holdings", headers=auth_headers(token)).json()
    for r in rows:
        if r["account_id"] == account_id and r["symbol"] == symbol:
            return Decimal(r["quantity"])
    return Decimal(0)


def test_sum_of_legs_equals_holding(client: TestClient, alice: dict) -> None:
    """Σ leg.quantity (active) == derived holding, per (account, asset)."""
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")

    _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                          "account_id": acc, "asset_id": irr, "quantity": "1000"})
    _post(client, token, {"type": "withdrawal", "occurred_at": "2026-01-02T00:00:00Z",
                          "account_id": acc, "asset_id": irr, "quantity": "150"})
    _post(client, token, {"type": "income", "occurred_at": "2026-01-03T00:00:00Z",
                          "account_id": acc, "asset_id": btc, "quantity": "0.2"})

    # Independent recomputation from the raw legs of every active transaction.
    expected: dict = {}
    page = client.get("/api/v1/transactions?page_size=100",
                      headers=auth_headers(token)).json()
    for txn in page["items"]:
        for leg in txn["legs"]:
            key = (leg["account_id"], leg["asset_id"])
            expected[key] = expected.get(key, Decimal(0)) + Decimal(leg["quantity"])

    holdings = client.get("/api/v1/holdings", headers=auth_headers(token)).json()
    derived = {(h["account_id"], h["asset_id"]): Decimal(h["quantity"]) for h in holdings}

    expected = {k: v for k, v in expected.items() if v != 0}
    assert derived == expected
    assert _holding(client, token, acc, "IRR") == Decimal("850")


def test_oversell_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                          "account_id": acc, "asset_id": irr, "quantity": "100"})
    resp = _post(client, token, {"type": "withdrawal", "occurred_at": "2026-01-02T00:00:00Z",
                                 "account_id": acc, "asset_id": irr, "quantity": "150"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unprocessable_entity"
    # holding unchanged
    assert _holding(client, token, acc, "IRR") == Decimal("100")


def test_oversell_via_trade_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                          "account_id": acc, "asset_id": irr, "quantity": "100"})
    resp = _post(client, token, {
        "type": "trade", "occurred_at": "2026-01-02T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": irr, "quantity": "-500"},
            {"account_id": acc, "asset_id": btc, "quantity": "0.01"},
        ],
    })
    assert resp.status_code == 422


def test_reverse_restores_holding(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    txn = _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                                "account_id": acc, "asset_id": irr, "quantity": "100"}).json()
    assert _holding(client, token, acc, "IRR") == Decimal("100")

    resp = client.post(
        f"/api/v1/transactions/{txn['id']}/reverse", headers=auth_headers(token)
    )
    assert resp.status_code == 201, resp.text
    reversal = resp.json()
    assert reversal["status"] == "reversed"
    assert reversal["reversal_of"] == txn["id"]

    # original is now reversed and excluded from holdings -> back to 0
    assert _holding(client, token, acc, "IRR") == Decimal(0)
    original = client.get(
        f"/api/v1/transactions/{txn['id']}", headers=auth_headers(token)
    ).json()
    assert original["status"] == "reversed"


def test_cannot_reverse_twice(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    txn = _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                                "account_id": acc, "asset_id": irr, "quantity": "100"}).json()
    client.post(f"/api/v1/transactions/{txn['id']}/reverse", headers=auth_headers(token))
    resp = client.post(
        f"/api/v1/transactions/{txn['id']}/reverse", headers=auth_headers(token)
    )
    assert resp.status_code == 422


def test_reverse_blocked_if_funds_spent(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    dep = _post(client, token, {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                                "account_id": acc, "asset_id": irr, "quantity": "100"}).json()
    _post(client, token, {"type": "withdrawal", "occurred_at": "2026-01-02T00:00:00Z",
                          "account_id": acc, "asset_id": irr, "quantity": "100"})
    # reversing the deposit would make holding -100
    resp = client.post(
        f"/api/v1/transactions/{dep['id']}/reverse", headers=auth_headers(token)
    )
    assert resp.status_code == 422


def test_no_cross_user_leak_in_holdings(
    client: TestClient, alice: dict, bob: dict
) -> None:
    a_acc = create_account(client, alice["token"])
    a_irr = asset_id(client, alice["token"], "IRR")
    _post(client, alice["token"], {"type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
                                   "account_id": a_acc, "asset_id": a_irr, "quantity": "100"})

    # Bob sees no holdings and cannot read Alice's transaction
    assert client.get("/api/v1/holdings", headers=auth_headers(bob["token"])).json() == []
    txns = client.get("/api/v1/transactions", headers=auth_headers(alice["token"])).json()
    other = txns["items"][0]["id"]
    resp = client.get(
        f"/api/v1/transactions/{other}", headers=auth_headers(bob["token"])
    )
    assert resp.status_code == 404
