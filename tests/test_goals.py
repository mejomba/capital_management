from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import (
    add_price,
    asset_id,
    auth_headers,
    create_account,
    post_txn,
)


def _create_goal(client, token, **body):
    return client.post("/api/v1/goals", json=body, headers=auth_headers(token))


def _progress(client, token, goal_id):
    return client.get(f"/api/v1/goals/{goal_id}", headers=auth_headers(token)).json()["progress"]


def test_target_net_worth_progress(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "400", "2026-01-01")
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
    })
    goal = _create_goal(client, token, type="target_net_worth", title="Reach 1000",
                        target_value="1000", currency="IRR").json()
    prog = _progress(client, token, goal["id"])
    # net worth 400 of 1000 -> 40%
    assert Decimal(prog["current_value"]) == Decimal("400")
    assert Decimal(prog["percent"]) == Decimal("40")
    assert Decimal(prog["remaining"]) == Decimal("600")
    assert prog["achieved"] is False


def test_target_allocation_progress(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    usd = asset_id(client, token, "USD")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "600", "2026-01-01")
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
    })  # crypto: 600 IRR
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": usd, "quantity": "8",
    })  # fiat: 8 * 50 = 400 IRR
    goal = _create_goal(client, token, type="target_allocation", title="50/50",
                        currency="IRR",
                        target_allocation={"crypto": "0.5", "fiat": "0.5"}).json()
    prog = _progress(client, token, goal["id"])
    # current weights crypto 0.6, fiat 0.4 ; tvd 0.1 -> 90%
    assert Decimal(prog["current_allocation"]["crypto"]) == Decimal("0.6")
    assert Decimal(prog["current_allocation"]["fiat"]) == Decimal("0.4")
    assert Decimal(prog["drift"]["crypto"]) == Decimal("0.1")
    assert Decimal(prog["drift"]["fiat"]) == Decimal("-0.1")
    assert Decimal(prog["percent"]) == Decimal("90")


def test_target_return_progress_pending(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    goal = _create_goal(client, token, type="target_return", title="20% return",
                        target_value="0.20").json()
    prog = _progress(client, token, goal["id"])
    assert prog["pending"] is True
    assert prog["percent"] is None


def test_custom_progress_null_until_achieved(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    goal = _create_goal(client, token, type="custom", title="Buy a house").json()
    assert _progress(client, token, goal["id"])["percent"] is None


def test_patch_goal_status(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    goal = _create_goal(client, token, type="custom", title="Buy a house").json()
    r = client.patch(f"/api/v1/goals/{goal['id']}", json={"status": "achieved"},
                     headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["status"] == "achieved"
    # custom progress now reports 100
    assert _progress(client, token, goal["id"])["percent"] == "100"


def test_list_and_auth(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _create_goal(client, token, type="custom", title="A")
    body = client.get("/api/v1/goals", headers=auth_headers(token)).json()
    assert body["total"] == 1
    assert client.get("/api/v1/goals").status_code == 401
