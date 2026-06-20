"""XIRR / TWR, native dual-currency, and the income double-count guard."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import (
    add_price,
    asset_id,
    auth_headers,
    create_account,
    deposit,
    post_txn,
)


def _perf(client, token, frm, to):
    return client.get(
        f"/api/v1/reports/performance?from={frm}&to={to}", headers=auth_headers(token)
    ).json()


def _approx(value, expected, tol=Decimal("0.0001")):
    return abs(Decimal(value) - Decimal(expected)) < tol


def test_xirr_twr_known_answer(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1100", "2027-01-01")
    # 1 BTC held at the window start, value 1000 -> 1100 over exactly 365 days
    deposit(client, token, acc, "BTC", "1", "2026-01-01T00:00:00Z")

    p = _perf(client, token, "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
    assert _approx(p["irr"]["xirr"], "0.10")
    assert _approx(p["irr"]["twr"], "0.10")
    # FX constant -> USD-native return equals IRR return here
    assert _approx(p["usd"]["twr"], "0.10")


def test_usd_native_strips_rial_devaluation(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="bank")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "USD", "IRR", "100", "2027-01-01")  # rial halves
    deposit(client, token, acc, "USD", "100", "2026-01-01T00:00:00Z")

    p = _perf(client, token, "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
    # rial value doubles (5000 -> 10000) = +100% nominal IRR
    assert _approx(p["irr"]["twr"], "1.0")
    # but in USD the purchasing power is unchanged ~ 0
    assert _approx(p["usd"]["twr"], "0", tol=Decimal("0.0001"))
    assert _approx(p["usd_based"], "0", tol=Decimal("0.0001"))


def test_income_not_counted_as_contribution(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2027-01-01")  # price flat
    deposit(client, token, acc, "BTC", "1", "2026-01-01T00:00:00Z")
    # staking reward (income) doubles holdings WITHOUT being a contribution
    post_txn(client, token, {
        "type": "income", "occurred_at": "2026-06-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
    })

    p = _perf(client, token, "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
    # value 1000 -> 2000 entirely from income => +100% return, not a flow.
    # If income were treated as a deposit, return would be ~0.
    assert _approx(p["irr"]["twr"], "1.0")
    assert Decimal(p["irr"]["xirr"]) > Decimal("0.9")


def test_xirr_diverges_from_twr_with_midperiod_contribution(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2026-07-01")  # flat first half
    add_price(client, token, "BTC", "IRR", "2000", "2027-01-01")  # doubles second half
    deposit(client, token, acc, "BTC", "1", "2026-01-01T00:00:00Z")
    # big contribution right before the doubling
    deposit(client, token, acc, "BTC", "9", "2026-07-01T00:00:00Z")

    p = _perf(client, token, "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
    # TWR: first half flat (x1), second half doubles (x2) => 100%
    assert _approx(p["irr"]["twr"], "1.0")
    # money-weighted return is higher: most capital was in during the doubling
    assert Decimal(p["irr"]["xirr"]) > Decimal(p["irr"]["twr"])


def test_real_return_formula(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-15")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-15")
    add_price(client, token, "BTC", "IRR", "1200", "2026-02-15")
    deposit(client, token, acc, "BTC", "1", "2026-01-15T00:00:00Z")
    # inflation over the two months in the window
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 1, "rate": "0.02"}, headers=auth_headers(token))
    client.post("/api/v1/inflation", json={"period_year": 2026, "period_month": 2, "rate": "0.03"}, headers=auth_headers(token))

    p = _perf(client, token, "2026-01-15T00:00:00Z", "2026-02-15T00:00:00Z")
    # nominal 20% ; cumulative inflation 1.02*1.03-1 = 0.0506
    assert _approx(p["inflation_cumulative"], "0.0506")
    expected_real = Decimal("1.2") / Decimal("1.0506") - Decimal(1)
    assert _approx(p["irr"]["real"], expected_real)


def test_performance_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/performance?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z").status_code == 401
