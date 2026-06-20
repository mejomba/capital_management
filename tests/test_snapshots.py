"""Snapshots are idempotent, fully recomputable, and hole-free."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import (
    add_price,
    asset_id,
    auth_headers,
    create_account,
    post_txn,
)


def _rebuild(client, token, frm, to):
    return client.post(
        "/api/v1/snapshots/rebuild",
        json={"from": frm, "to": to},
        headers=auth_headers(token),
    )


def _snapshots(client, token, frm=None, to=None):
    q = []
    if frm:
        q.append(f"from={frm}")
    if to:
        q.append(f"to={to}")
    qs = ("?" + "&".join(q)) if q else ""
    return client.get(f"/api/v1/snapshots{qs}", headers=auth_headers(token)).json()


def _seed(client, token):
    acc = create_account(client, token, type="exchange")
    btc = asset_id(client, token, "BTC")
    add_price(client, token, "USD", "IRR", "50", "2026-01-01")
    add_price(client, token, "BTC", "IRR", "400", "2026-01-01")
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": btc, "quantity": "1",
        "unit_price": "100", "price_currency": "IRR",
    })
    return acc, btc


def test_rebuild_is_idempotent(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _seed(client, token)
    r1 = _rebuild(client, token, "2026-01-01", "2026-01-01")
    assert r1.json()["created"] == 1
    first = _snapshots(client, token)
    # running again must not create a duplicate, and values must match
    r2 = _rebuild(client, token, "2026-01-01", "2026-01-01")
    assert r2.json()["created"] == 1
    again = _snapshots(client, token)
    assert len(first) == 1 and len(again) == 1
    assert first[0]["net_worth_irr"] == again[0]["net_worth_irr"]


def test_backfill_range_and_nearest_price(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _seed(client, token)  # BTC priced only on 2026-01-01
    created = _rebuild(client, token, "2026-01-01", "2026-01-05").json()["created"]
    assert created == 5
    rows = _snapshots(client, token)
    assert len(rows) == 5
    # days after 01-01 have no BTC price of their own -> nearest earlier (400) is
    # used, so no holes and the value stays 400 IRR.
    for row in rows:
        assert Decimal(row["total_assets_irr"]) == Decimal("400")
        assert Decimal(row["net_worth_irr"]) == Decimal("400")


def test_unvalued_asset_marked_not_errored(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    acc = create_account(client, token, type="exchange")
    eth = asset_id(client, token, "ETH")
    # deposit ETH but never price it, and no FX either
    post_txn(client, token, {
        "type": "deposit", "occurred_at": "2026-01-01T00:00:00Z",
        "account_id": acc, "asset_id": eth, "quantity": "5",
    })
    assert _rebuild(client, token, "2026-01-01", "2026-01-01").status_code == 201
    snap = _snapshots(client, token)[0]
    assert Decimal(snap["total_assets_irr"]) == Decimal("0")  # nothing valued
    unvalued = snap["breakdown"]["unvalued_assets"]
    assert any(u["symbol"] == "ETH" and Decimal(u["quantity"]) == Decimal("5") for u in unvalued)


def test_net_worth_series_matches_snapshots(client: TestClient, alice: dict) -> None:
    token = alice["token"]
    _seed(client, token)
    _rebuild(client, token, "2026-01-01", "2026-01-03")
    snaps = _snapshots(client, token)
    series = client.get(
        "/api/v1/reports/net-worth?from=2026-01-01&to=2026-01-03",
        headers=auth_headers(token),
    ).json()["series"]
    assert len(series) == len(snaps) == 3
    for snap, point in zip(snaps, series):
        assert snap["as_of"] == point["as_of"]
        assert snap["net_worth_irr"] == point["net_worth_irr"]
