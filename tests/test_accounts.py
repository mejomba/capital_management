from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _create(client: TestClient, token: str, **kwargs) -> dict:
    body = {"name": "Main bank", "type": "bank"}
    body.update(kwargs)
    resp = client.post("/api/v1/accounts", json=body, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_get_account(client: TestClient, alice: dict) -> None:
    created = _create(client, alice["token"], name="Binance", type="exchange")
    assert created["name"] == "Binance"
    assert created["type"] == "exchange"
    assert created["user_id"] == alice["user"]["id"]

    resp = client.get(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_list_accounts_paginated(client: TestClient, alice: dict) -> None:
    for i in range(3):
        _create(client, alice["token"], name=f"acc-{i}")
    resp = client.get(
        "/api/v1/accounts?page=1&page_size=2", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


def test_update_account(client: TestClient, alice: dict) -> None:
    created = _create(client, alice["token"])
    resp = client.patch(
        f"/api/v1/accounts/{created['id']}",
        json={"name": "Renamed", "note": "primary"},
        headers=auth_headers(alice["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["note"] == "primary"


def test_soft_delete_account(client: TestClient, alice: dict) -> None:
    created = _create(client, alice["token"])
    resp = client.delete(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 204

    # gone from reads
    resp = client.get(
        f"/api/v1/accounts/{created['id']}", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 404

    resp = client.get("/api/v1/accounts", headers=auth_headers(alice["token"]))
    assert resp.json()["total"] == 0


def test_get_missing_account_404(client: TestClient, alice: dict) -> None:
    resp = client.get(
        "/api/v1/accounts/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(alice["token"]),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_accounts_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/accounts").status_code == 401
