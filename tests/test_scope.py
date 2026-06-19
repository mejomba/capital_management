"""User-scope isolation: one user must never see/touch another user's data."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_user_cannot_see_others_account(
    client: TestClient, alice: dict, bob: dict
) -> None:
    created = client.post(
        "/api/v1/accounts",
        json={"name": "Alice bank", "type": "bank"},
        headers=auth_headers(alice["token"]),
    ).json()

    # Bob's listing is empty
    resp = client.get("/api/v1/accounts", headers=auth_headers(bob["token"]))
    assert resp.json()["total"] == 0

    # Bob cannot fetch it directly
    resp = client.get(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(bob["token"])
    )
    assert resp.status_code == 404


def test_user_cannot_update_or_delete_others_account(
    client: TestClient, alice: dict, bob: dict
) -> None:
    created = client.post(
        "/api/v1/accounts",
        json={"name": "Alice bank", "type": "bank"},
        headers=auth_headers(alice["token"]),
    ).json()

    resp = client.patch(
        f"/api/v1/accounts/{created['id']}",
        json={"name": "hijacked"},
        headers=auth_headers(bob["token"]),
    )
    assert resp.status_code == 404

    resp = client.delete(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(bob["token"])
    )
    assert resp.status_code == 404

    # Alice's account is intact
    resp = client.get(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice bank"


def test_user_cannot_see_others_custom_asset(
    client: TestClient, alice: dict, bob: dict
) -> None:
    created = client.post(
        "/api/v1/assets",
        json={
            "symbol": "ALICEHOME",
            "name": "Alice apartment",
            "asset_class": "real_estate",
            "unit": "unit",
            "quote_currency": "IRR",
        },
        headers=auth_headers(alice["token"]),
    ).json()

    resp = client.get(
        f"/api/v1/assets/{created['id']}", headers=auth_headers(bob["token"])
    )
    assert resp.status_code == 404

    # but Bob still sees shared system assets
    resp = client.get(
        "/api/v1/assets?q=BTC", headers=auth_headers(bob["token"])
    )
    symbols = {a["symbol"] for a in resp.json()["items"]}
    assert "BTC" in symbols
