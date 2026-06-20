"""Derived liability balance with no interest double-counting."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import add_liability_event, auth_headers, create_liability


def _balance(client, token, liability_id) -> dict:
    resp = client.get(f"/api/v1/liabilities/{liability_id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["balance"]


def test_disbursement_then_repayment(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    lia = create_liability(client, token, principal="1000", currency="IRR")
    add_liability_event(client, token, lia["id"], type="disbursement",
                        amount="1000", currency="IRR", occurred_at="2026-01-01T00:00:00Z")
    add_liability_event(client, token, lia["id"], type="repayment",
                        amount="300", currency="IRR", occurred_at="2026-02-01T00:00:00Z",
                        principal_component="300", interest_component="0")

    bal = _balance(client, token, lia["id"])
    assert Decimal(bal["principal_outstanding"]) == Decimal("700")
    assert Decimal(bal["interest_unpaid"]) == Decimal("0")
    assert Decimal(bal["total_outstanding"]) == Decimal("700")


def test_interest_not_double_counted(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    lia = create_liability(client, token, principal="100", currency="IRR")
    # 100 principal, 10 interest recognised
    add_liability_event(client, token, lia["id"], type="disbursement",
                        amount="100", currency="IRR", occurred_at="2026-01-01T00:00:00Z")
    add_liability_event(client, token, lia["id"], type="interest",
                        amount="10", currency="IRR", occurred_at="2026-01-31T00:00:00Z")
    # pay an installment of 30, split 25 principal / 5 interest
    add_liability_event(client, token, lia["id"], type="repayment",
                        amount="30", currency="IRR", occurred_at="2026-02-01T00:00:00Z",
                        principal_component="25", interest_component="5")

    bal = _balance(client, token, lia["id"])
    # principal: 100 - 25 = 75 ; interest: 10 - 5 = 5 ; total 80
    # interest counted exactly once (not 100-30 + 10 = 80 by accident; verify components)
    assert Decimal(bal["principal_outstanding"]) == Decimal("75")
    assert Decimal(bal["interest_unpaid"]) == Decimal("5")
    assert Decimal(bal["total_outstanding"]) == Decimal("80")


def test_repayment_component_checksum_enforced(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    lia = create_liability(client, token, currency="IRR")
    r = add_liability_event(client, token, lia["id"], type="repayment",
                            amount="30", currency="IRR", occurred_at="2026-02-01T00:00:00Z",
                            principal_component="25", interest_component="10")  # 35 != 30
    assert r.status_code == 422


def test_event_currency_must_match(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    lia = create_liability(client, token, currency="IRR")
    r = add_liability_event(client, token, lia["id"], type="disbursement",
                            amount="100", currency="USD", occurred_at="2026-01-01T00:00:00Z")
    assert r.status_code == 422


def test_repayment_defaults_to_principal(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    lia = create_liability(client, token, currency="IRR")
    add_liability_event(client, token, lia["id"], type="disbursement",
                        amount="500", currency="IRR", occurred_at="2026-01-01T00:00:00Z")
    # no components -> treated as pure principal repayment
    add_liability_event(client, token, lia["id"], type="repayment",
                        amount="200", currency="IRR", occurred_at="2026-02-01T00:00:00Z")
    bal = _balance(client, token, lia["id"])
    assert Decimal(bal["principal_outstanding"]) == Decimal("300")
    assert Decimal(bal["interest_unpaid"]) == Decimal("0")


def test_liabilities_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/liabilities").status_code == 401
