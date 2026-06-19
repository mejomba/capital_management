from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_user


def test_register_returns_user_and_token(client: TestClient) -> None:
    data = register_user(client)
    assert "token" in data and data["token"]
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["display_name"] == "Alice"
    assert "id" in data["user"]
    # password material must never be returned
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    register_user(client)
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_register_weak_password_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unprocessable_entity"


def test_login_success(client: TestClient) -> None:
    register_user(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_wrong_password(client: TestClient) -> None:
    register_user(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_me_with_invalid_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me", headers=auth_headers("not-a-jwt"))
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    data = register_user(client)
    resp = client.get("/api/v1/auth/me", headers=auth_headers(data["token"]))
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"
