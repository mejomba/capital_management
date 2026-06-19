from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _create(client: TestClient, token: str, **kwargs) -> dict:
    body = {
        "symbol": "MYHOME",
        "name": "My apartment",
        "asset_class": "real_estate",
        "unit": "unit",
        "quote_currency": "IRR",
    }
    body.update(kwargs)
    resp = client.post("/api/v1/assets", json=body, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_system_assets_are_seeded_and_visible(client: TestClient, alice: dict) -> None:
    resp = client.get(
        "/api/v1/assets?page_size=100", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 200
    symbols = {a["symbol"] for a in resp.json()["items"] if a["user_id"] is None}
    assert {"IRR", "USD", "EUR", "BTC", "ETH", "XAU", "XAG"} <= symbols


def test_filter_by_class(client: TestClient, alice: dict) -> None:
    resp = client.get(
        "/api/v1/assets?class=crypto&page_size=100",
        headers=auth_headers(alice["token"]),
    )
    assert resp.status_code == 200
    classes = {a["asset_class"] for a in resp.json()["items"]}
    assert classes == {"crypto"}
    symbols = {a["symbol"] for a in resp.json()["items"]}
    assert {"BTC", "ETH"} <= symbols


def test_search_query(client: TestClient, alice: dict) -> None:
    resp = client.get(
        "/api/v1/assets?q=gold", headers=auth_headers(alice["token"])
    )
    assert resp.status_code == 200
    symbols = {a["symbol"] for a in resp.json()["items"]}
    assert "XAU" in symbols


def test_create_custom_asset(client: TestClient, alice: dict) -> None:
    created = _create(client, alice["token"])
    assert created["user_id"] == alice["user"]["id"]
    assert created["asset_class"] == "real_estate"
    assert created["is_active"] is True


def test_update_own_asset(client: TestClient, alice: dict) -> None:
    created = _create(client, alice["token"])
    resp = client.patch(
        f"/api/v1/assets/{created['id']}",
        json={"name": "Renamed property", "is_active": False},
        headers=auth_headers(alice["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed property"
    assert resp.json()["is_active"] is False


def test_cannot_update_system_asset(client: TestClient, alice: dict) -> None:
    resp = client.get(
        "/api/v1/assets?q=BTC", headers=auth_headers(alice["token"])
    )
    btc = next(a for a in resp.json()["items"] if a["symbol"] == "BTC")
    resp = client.patch(
        f"/api/v1/assets/{btc['id']}",
        json={"name": "hacked"},
        headers=auth_headers(alice["token"]),
    )
    assert resp.status_code == 404


def test_assets_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/assets").status_code == 401
