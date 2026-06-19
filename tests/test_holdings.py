from fastapi.testclient import TestClient

from tests.conftest import asset_id, auth_headers, create_account


def _deposit(client, token, acc, asset, qty, when="2026-01-01T00:00:00Z"):
    return client.post(
        "/api/v1/transactions",
        json={
            "type": "deposit", "occurred_at": when,
            "account_id": acc, "asset_id": asset, "quantity": qty,
        },
        headers=auth_headers(token),
    )


def test_holdings_by_account_asset(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    _deposit(client, token, acc, irr, "100")
    _deposit(client, token, acc, irr, "50", "2026-01-02T00:00:00Z")

    resp = client.get("/api/v1/holdings", headers=auth_headers(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["account_id"] == acc
    assert rows[0]["symbol"] == "IRR"
    assert rows[0]["quantity"] == "150.000000000000000000"


def test_holdings_by_asset_aggregates_accounts(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    a1 = create_account(client, token, name="a1")
    a2 = create_account(client, token, name="a2")
    irr = asset_id(client, token, "IRR")
    _deposit(client, token, a1, irr, "100")
    _deposit(client, token, a2, irr, "25")

    resp = client.get("/api/v1/holdings/by-asset", headers=auth_headers(token))
    assert resp.status_code == 200
    rows = resp.json()
    irr_row = next(r for r in rows if r["symbol"] == "IRR")
    assert irr_row["quantity"] == "125.000000000000000000"


def test_holdings_by_class_groups(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    irr = asset_id(client, token, "IRR")
    btc = asset_id(client, token, "BTC")
    _deposit(client, token, acc, irr, "100")
    _deposit(client, token, acc, btc, "0.5")

    resp = client.get("/api/v1/holdings/by-class", headers=auth_headers(token))
    assert resp.status_code == 200
    by_class = {r["asset_class"]: r["items"] for r in resp.json()}
    assert "fiat" in by_class and "crypto" in by_class
    assert {i["symbol"] for i in by_class["crypto"]} == {"BTC"}


def test_holdings_as_of_filters_by_time(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token)
    irr = asset_id(client, token, "IRR")
    _deposit(client, token, acc, irr, "100", "2026-01-01T00:00:00Z")
    _deposit(client, token, acc, irr, "100", "2026-02-01T00:00:00Z")

    resp = client.get(
        "/api/v1/holdings?as_of=2026-01-15T00:00:00Z", headers=auth_headers(token)
    )
    assert resp.json()[0]["quantity"] == "100.000000000000000000"


def test_holdings_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/holdings").status_code == 401
