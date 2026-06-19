from fastapi.testclient import TestClient

from tests.conftest import asset_id, auth_headers, create_account


def _post(client: TestClient, token: str, body: dict):
    return client.post(
        "/api/v1/transactions", json=body, headers=auth_headers(token)
    )


def test_deposit_creates_single_positive_leg(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    resp = _post(
        client,
        token,
        {
            "type": "deposit",
            "occurred_at": "2026-01-01T00:00:00Z",
            "account_id": acc,
            "asset_id": irr,
            "quantity": "100000000",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "deposit"
    assert body["status"] == "active"
    assert len(body["legs"]) == 1
    assert body["legs"][0]["quantity"] == "100000000.000000000000000000"


def test_withdrawal_stores_negative_leg(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": irr, "quantity": "100",
    })
    resp = _post(client, token, {
        "type": "withdrawal", "occurred_at": "2026-01-02T00:00:00Z",
        "account_id": acc, "asset_id": irr, "quantity": "40",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["legs"][0]["quantity"].startswith("-40")


def test_trade_two_opposite_legs(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": irr, "quantity": "500000000",
    })
    resp = _post(client, token, {
        "type": "trade", "occurred_at": "2026-01-03T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": irr, "quantity": "-500000000",
             "unit_price": "1", "price_currency": "IRR"},
            {"account_id": acc, "asset_id": btc, "quantity": "0.01",
             "unit_price": "50000000000", "price_currency": "IRR"},
        ],
        "fee": "100000", "fee_currency": "IRR",
    })
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["legs"]) == 2


def test_trade_same_asset_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    resp = _post(client, token, {
        "type": "trade", "occurred_at": "2026-01-03T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": irr, "quantity": "-100"},
            {"account_id": acc, "asset_id": irr, "quantity": "100"},
        ],
    })
    assert resp.status_code == 422


def test_trade_same_sign_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    resp = _post(client, token, {
        "type": "trade", "occurred_at": "2026-01-03T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": irr, "quantity": "100"},
            {"account_id": acc, "asset_id": btc, "quantity": "100"},
        ],
    })
    assert resp.status_code == 422


def test_transfer_with_fee_consistent(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    exchange = create_account(client, token, name="exchange", type="exchange")
    wallet = create_account(client, token, name="wallet", type="wallet")
    btc = asset_id(client, token, "BTC")
    _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": exchange, "asset_id": btc, "quantity": "0.01",
    })
    resp = _post(client, token, {
        "type": "transfer", "occurred_at": "2026-01-04T00:00:00Z",
        "legs": [
            {"account_id": exchange, "asset_id": btc, "quantity": "-0.01"},
            {"account_id": wallet, "asset_id": btc, "quantity": "0.0099"},
        ],
        "fee": "0.0001", "fee_currency": "BTC",
    })
    assert resp.status_code == 201, resp.text


def test_transfer_inconsistent_fee_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    exchange = create_account(client, token, name="exchange", type="exchange")
    wallet = create_account(client, token, name="wallet", type="wallet")
    btc = asset_id(client, token, "BTC")
    _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": exchange, "asset_id": btc, "quantity": "0.02",
    })
    resp = _post(client, token, {
        "type": "transfer", "occurred_at": "2026-01-04T00:00:00Z",
        "legs": [
            {"account_id": exchange, "asset_id": btc, "quantity": "-0.01"},
            {"account_id": wallet, "asset_id": btc, "quantity": "0.0099"},
        ],
        # missing fee -> sum != 0 -> inconsistent
    })
    assert resp.status_code == 422


def test_transfer_same_account_rejected(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "0.01",
    })
    resp = _post(client, token, {
        "type": "transfer", "occurred_at": "2026-01-04T00:00:00Z",
        "legs": [
            {"account_id": acc, "asset_id": btc, "quantity": "-0.005"},
            {"account_id": acc, "asset_id": btc, "quantity": "0.005"},
        ],
    })
    assert resp.status_code == 422


def test_cannot_reference_other_users_account(
    client: TestClient, alice: dict, bob: dict
) -> None:
    bob_acc = create_account(client, bob["token"])
    irr = asset_id(client, alice["token"], "IRR")
    resp = _post(client, alice["token"], {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": bob_acc, "asset_id": irr, "quantity": "100",
    })
    assert resp.status_code == 422


def test_list_filters_and_pagination(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    for i in range(3):
        _post(client, token, {
            "type": "deposit", "occurred_at": f"2026-01-0{i+1}T00:00:00Z",
            "account_id": acc, "asset_id": irr, "quantity": "10",
        })
    resp = client.get(
        "/api/v1/transactions?type=deposit&page=1&page_size=2",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_delete_transaction_soft(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    txn = _post(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": irr, "quantity": "100",
    }).json()
    resp = client.delete(
        f"/api/v1/transactions/{txn['id']}", headers=auth_headers(token)
    )
    assert resp.status_code == 204
    resp = client.get(
        f"/api/v1/transactions/{txn['id']}", headers=auth_headers(token)
    )
    assert resp.status_code == 404


def test_transactions_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/transactions").status_code == 401
