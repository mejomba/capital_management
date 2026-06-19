# Wealth Manager — Backend

Source of truth for the data model, financial logic, and API contract.
Stack: FastAPI · PostgreSQL · SQLAlchemy 2.x · Alembic · Pydantic v2.

This repository currently implements **Milestone M1** (project bootstrap +
authentication + accounts/assets CRUD). See `ROADMAP.md` for the full plan and
`CLAUDE.backend.md` for the non-negotiable engineering rules.

## Requirements

- Python 3.11+
- PostgreSQL 16 (via `docker-compose` or a local server)

## Setup

```bash
# 1. Start the database
docker compose up -d db          # exposes postgres on localhost:5432 (user/pass/db = cm)

# 2. Create the environment and install dependencies
uv venv .venv && . .venv/bin/activate
uv pip install -e ".[dev]"

# 3. Configure
cp .env.example .env             # adjust DATABASE_URL / SECRET_KEY as needed

# 4. Apply migrations (creates schema + seeds system assets)
alembic upgrade head

# 5. Run the API
uvicorn app.main:app --reload
```

Interactive docs: <http://localhost:8000/docs>.

## Configuration

Settings are read from environment variables / `.env` (see `app/core/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cm@127.0.0.1:5432/cm` | SQLAlchemy URL (psycopg v3) |
| `SECRET_KEY` | dev placeholder | JWT signing key (use ≥32 bytes in prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access-token lifetime |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `API_V1_PREFIX` | `/api/v1` | API base path |

## Tests

Tests run against a separate `cm_test` database.

```bash
createdb -h 127.0.0.1 -U cm cm_test   # one-time
DATABASE_URL=postgresql+psycopg://cm@127.0.0.1:5432/cm_test python -m pytest
```

The suite covers auth (register/login/me), accounts & assets CRUD, pagination,
soft delete, system-asset seeding, and cross-user scope isolation.

## Conventions (M1-relevant subset)

- **Money:** every monetary / quantity column is `NUMERIC(38,18)` (`app.models.base.Money`)
  and is serialised as a **string** in the API (`MoneyStr`) to preserve precision.
- **Scope:** every query is scoped by `user_id`; assets with `user_id IS NULL` are
  shared system assets (read-only for users).
- **Soft delete:** records are never hard-deleted — `deleted_at` is set and filtered.
- **Timestamps:** stored as UTC; the API emits ISO-8601.
- **Errors:** uniform envelope `{"error": {"code", "message", "details?}}`.
- **Pagination:** `?page=&page_size=` → `{items, total, page, page_size}`.

## OpenAPI

`openapi.json` at the repo root is generated from the running app:

```bash
python scripts/export_openapi.py
```
