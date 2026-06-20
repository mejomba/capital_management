from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_price, auth_headers, create_account, deposit


def _setup(client, token, growth):
    acc = create_account(client, token, type="exchange")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "1000", "2026-01-01")
    deposit(client, token, acc, "BTC", "1", "2026-01-01T00:00:00Z")  # crypto 1000 IRR
    client.put("/api/v1/assumptions", json={
        "display_currency": "both", "hurdle_mode": "inflation",
        "growth_assumptions": {"crypto": growth},
    }, headers=auth_headers(token))


def test_projection_realistic_growth(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup(client, token, "0.12")
    rep = client.get(
        "/api/v1/reports/projection?horizon_months=12&monthly_contribution=0&scenario=realistic",
        headers=auth_headers(token),
    ).json()
    series = rep["scenarios"]["realistic"]
    assert len(series) == 12
    # 1000 grown by 12% annual over 12 months ~= 1120
    final = Decimal(series[-1]["net_worth_irr"])
    assert abs(final - Decimal("1120")) < Decimal("1")
    # USD via current FX (50)
    assert abs(Decimal(series[-1]["net_worth_usd"]) - final / Decimal("50")) < Decimal("0.01")


def test_three_scenarios_ordered(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup(client, token, "0.12")
    rep = client.get(
        "/api/v1/reports/projection?horizon_months=12&monthly_contribution=0",
        headers=auth_headers(token),
    ).json()
    assert set(rep["scenarios"]) == {"pessimistic", "realistic", "optimistic"}
    p = Decimal(rep["scenarios"]["pessimistic"][-1]["net_worth_irr"])
    r = Decimal(rep["scenarios"]["realistic"][-1]["net_worth_irr"])
    o = Decimal(rep["scenarios"]["optimistic"][-1]["net_worth_irr"])
    assert p < r < o


def test_projection_with_contribution(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _setup(client, token, "0")  # no growth, isolate contributions
    rep = client.get(
        "/api/v1/reports/projection?horizon_months=10&monthly_contribution=100&scenario=realistic",
        headers=auth_headers(token),
    ).json()
    # 1000 start + 10 * 100 contributions, no growth = 2000
    final = Decimal(rep["scenarios"]["realistic"][-1]["net_worth_irr"])
    assert abs(final - Decimal("2000")) < Decimal("0.01")
