"""Assumptions, inflation series, hurdle resolution, and the comparison report."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import (
    add_price,
    auth_headers,
    create_account,
    deposit,
)


def test_assumptions_get_default_and_put(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    default = client.get("/api/v1/assumptions", headers=auth_headers(token)).json()
    assert default["hurdle_mode"] == "inflation"  # transient default

    put = client.put("/api/v1/assumptions", json={
        "display_currency": "both", "hurdle_mode": "fixed",
        "hurdle_fixed_rate": "0.25",
        "growth_assumptions": {"crypto": "0.2"},
    }, headers=auth_headers(token)).json()
    assert put["hurdle_mode"] == "fixed"
    assert Decimal(put["hurdle_fixed_rate"]) == Decimal("0.25")
    # persisted
    again = client.get("/api/v1/assumptions", headers=auth_headers(token)).json()
    assert again["growth_assumptions"]["crypto"] == "0.2"


def test_inflation_upsert(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 1, "rate": "0.02"}, headers=auth_headers(token))
    # same period again -> upsert, not duplicate
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 1, "rate": "0.04"}, headers=auth_headers(token))
    rows = client.get("/api/v1/inflation", headers=auth_headers(token)).json()
    assert len(rows) == 1
    assert Decimal(rows[0]["rate"]) == Decimal("0.04")


def _comparison(client, token, frm, to):
    return client.get(
        f"/api/v1/reports/inflation-comparison?from={frm}&to={to}",
        headers=auth_headers(token),
    ).json()


def _setup_return(client, token):
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-15")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-15")
    add_price(client, token, "BTC", "IRR", "1200", "2026-02-15")  # +20%
    deposit(client, token, acc, "BTC", "1", "2026-01-15T00:00:00Z")


def test_hurdle_fixed_mode(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup_return(client, token)
    client.put("/api/v1/assumptions", json={
        "display_currency": "both", "hurdle_mode": "fixed", "hurdle_fixed_rate": "0.30",
    }, headers=auth_headers(token))
    rep = _comparison(client, token, "2026-01-15T00:00:00Z", "2026-02-15T00:00:00Z")
    assert rep["hurdle"]["mode"] == "fixed"
    assert Decimal(rep["hurdle"]["rate"]) == Decimal("0.30")
    # nominal 20% < hurdle 30%
    assert rep["beats_hurdle"] is False


def test_hurdle_inflation_mode(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup_return(client, token)
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 1, "rate": "0.02"}, headers=auth_headers(token))
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 2, "rate": "0.03"}, headers=auth_headers(token))
    client.put("/api/v1/assumptions", json={
        "display_currency": "both", "hurdle_mode": "inflation",
    }, headers=auth_headers(token))
    rep = _comparison(client, token, "2026-01-15T00:00:00Z", "2026-02-15T00:00:00Z")
    assert rep["hurdle"]["mode"] == "inflation"
    assert Decimal(rep["hurdle"]["rate"]) == Decimal("0.0506")
    # nominal 20% beats inflation 5.06%
    assert rep["beats_inflation"] is True
    assert rep["beats_hurdle"] is True


def test_hurdle_usd_growth_mode(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup_return(client, token)
    # FX from 50 -> 60 over the window
    add_price(client, token, "USD", "IRR", "60", "2026-02-15")
    client.put("/api/v1/assumptions", json={
        "display_currency": "both", "hurdle_mode": "usd_growth",
    }, headers=auth_headers(token))
    rep = _comparison(client, token, "2026-01-15T00:00:00Z", "2026-02-15T00:00:00Z")
    assert rep["hurdle"]["mode"] == "usd_growth"
    # 60/50 - 1 = 0.2
    assert Decimal(rep["hurdle"]["rate"]) == Decimal("0.2")
