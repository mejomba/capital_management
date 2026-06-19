import os

# Point the whole app at the test database BEFORE importing any app module
# (settings are cached on first import and env vars win over .env).
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://cm@127.0.0.1:5432/cm_test"
)
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-at-least-32-bytes-long-000"
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    """Run migrations on the test database (down to base, then up to head)."""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Reset per-user data between tests; keep seeded system assets."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_log"))
        conn.execute(text("DELETE FROM transaction_leg"))
        conn.execute(text("DELETE FROM transaction"))
        conn.execute(text("DELETE FROM account"))
        conn.execute(text("DELETE FROM asset WHERE user_id IS NOT NULL"))
        conn.execute(text('DELETE FROM "user"'))
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def register_user(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "password123",
    display_name: str = "Alice",
) -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_account(
    client: TestClient, token: str, name: str = "Main", type: str = "bank"
) -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "type": type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def asset_id(client: TestClient, token: str, symbol: str) -> str:
    resp = client.get(
        f"/api/v1/assets?q={symbol}&page_size=100", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    return next(a["id"] for a in resp.json()["items"] if a["symbol"] == symbol)


@pytest.fixture()
def alice(client: TestClient) -> dict:
    data = register_user(client, email="alice@example.com")
    return {"token": data["token"], "user": data["user"]}


@pytest.fixture()
def bob(client: TestClient) -> dict:
    data = register_user(client, email="bob@example.com", display_name="Bob")
    return {"token": data["token"], "user": data["user"]}
