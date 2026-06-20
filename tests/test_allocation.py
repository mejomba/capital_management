from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, auth_headers, create_account, deposit


def test_allocation_drift_and_rebalance(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "600", "2026-01-01")
    deposit(client, token, acc, "BTC", "1", "2026-01-01T00:00:00Z")   # crypto 600
    deposit(client, token, acc, "USD", "8", "2026-01-01T00:00:00Z")   # fiat 8*50=400

    client.post("/api/v1/goals", json={
        "type": "target_allocation", "title": "50/50",
        "target_allocation": {"crypto": "0.5", "fiat": "0.5"},
    }, headers=auth_headers(token))

    rep = client.get(
        "/api/v1/reports/allocation?currency=IRR&as_of=2026-01-02T00:00:00Z",
        headers=auth_headers(token),
    ).json()

    assert Decimal(rep["total_value"]) == Decimal("1000")
    assert Decimal(rep["current"]["crypto"]) == Decimal("0.6")
    assert Decimal(rep["current"]["fiat"]) == Decimal("0.4")
    assert Decimal(rep["drift"]["crypto"]) == Decimal("0.1")
    assert Decimal(rep["drift"]["fiat"]) == Decimal("-0.1")

    by_class = {r["asset_class"]: r for r in rep["rebalance"]}
    # crypto over-weight -> sell 100 ; fiat under-weight -> buy 100
    assert by_class["crypto"]["action"] == "sell"
    assert Decimal(by_class["crypto"]["amount"]) == Decimal("100")
    assert by_class["fiat"]["action"] == "buy"
    assert Decimal(by_class["fiat"]["amount"]) == Decimal("100")

    # rebalancing is self-funding: deltas sum to zero
    assert sum(Decimal(r["delta"]) for r in rep["rebalance"]) == Decimal("0")
    # applying each delta lands exactly on the target value
    for r in rep["rebalance"]:
        assert Decimal(r["current_value"]) + Decimal(r["delta"]) == Decimal(r["target_value"])
