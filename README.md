# Wealth Manager — Backend (مدیریت سرمایه)

بک‌اند سیستم مدیریت سرمایه و **منبع حقیقت** کل پروژه: مدل داده، منطق مالی، و قرارداد API.
فرانت‌اند فقط مصرف‌کننده‌ی این API است و هیچ منطق مالی‌ای را بازتولید نمی‌کند.

**Stack:** FastAPI · PostgreSQL 16 · SQLAlchemy 2.x · Alembic · Pydantic v2 · PyJWT · Argon2.

این ریپو **Milestone‌های M1 تا M5** را به‌صورت کامل و تست‌شده پیاده می‌کند:

| Milestone | محتوا |
|---|---|
| **M1** | راه‌اندازی، احراز هویت (JWT)، CRUD حساب و دارایی، seed دارایی‌های سیستمی |
| **M2** | دفتر تراکنش + پایه‌ها، موجودی مشتق‌شده، reverse/soft-delete، audit log |
| **M3** | قیمت دستی + نرخ FX، لات و FIFO، سود/زیان محقق‌شده و نشده‌ی دوارزی (IRR/USD) |
| **M4** | بدهی و رویدادها (مانده‌ی مشتق‌شده)، اسنپ‌شات پرتفو، ارزش خالص، اهداف |
| **M5** | XIRR/TWR، nominal/real/usd-based، تورم و hurdle، تخصیص و بازتعادل، پیش‌بینی |

قواعد قطعی مهندسی در `CLAUDE.backend.md` و نقشه‌ی راه در `ROADMAP.md` آمده است.

---

## پیش‌نیازها

- Python 3.11+
- PostgreSQL 16 (با `docker-compose` یا سرور محلی)
- (اختیاری) [`uv`](https://github.com/astral-sh/uv) برای مدیریت سریع محیط — یا همان `python -m venv` + `pip`.

## راه‌اندازی سریع

```bash
# ۱) دیتابیس را بالا بیاور (postgres روی localhost:5432، user/pass/db = cm)
docker compose up -d db

# ۲) محیط مجازی و نصب وابستگی‌ها
uv venv .venv && . .venv/bin/activate
uv pip install -e ".[dev]"
#   جایگزین بدون uv:
#   python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

# ۳) پیکربندی
cp .env.example .env             # در صورت نیاز DATABASE_URL / SECRET_KEY را تنظیم کن

# ۴) اجرای migrationها (ساخت schema + seed دارایی‌های سیستمی)
alembic upgrade head

# ۵) اجرای API
uvicorn app.main:app --reload
```

- مستندات تعاملی (Swagger UI): <http://localhost:8000/docs>
- مستندات ReDoc: <http://localhost:8000/redoc>
- سلامت سرویس: <http://localhost:8000/health>

## پیکربندی

تنظیمات از متغیرهای محیطی / فایل `.env` خوانده می‌شوند (`app/core/config.py`):

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cm:cm@127.0.0.1:5432/cm` | آدرس SQLAlchemy (درایور psycopg v3)؛ شامل پسورد `user:password@` |
| `SECRET_KEY` | placeholder توسعه | کلید امضای JWT (در production حداقل ۳۲ بایت) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | طول عمر access token |
| `JWT_ALGORITHM` | `HS256` | الگوریتم JWT |
| `API_V1_PREFIX` | `/api/v1` | مسیر پایه‌ی API |
| `ENABLE_SCHEDULER` | `false` | فعال‌سازی job روزانه‌ی ساخت اسنپ‌شات |
| `SNAPSHOT_HOUR_UTC` / `SNAPSHOT_MINUTE_UTC` | `0` / `30` | زمان اجرای job روزانه (UTC) |

## دیتابیس و Migrationها

```bash
alembic upgrade head                 # اعمال تا آخرین نسخه
alembic downgrade -1                 # یک قدم به عقب
alembic revision --autogenerate -m "msg"   # ساخت migration جدید از روی مدل‌ها
alembic current                      # نسخه‌ی فعلی
```

migrationها در `migrations/versions/` با نام‌گذاری `000N_*` هستند و enum typeها را در downgrade پاک می‌کنند (roundtrip up/down تمیز است).

## تست‌ها

تست‌ها روی یک دیتابیس جدا (`cm_test`) اجرا می‌شوند و خودشان schema را می‌سازند/پاک می‌کنند:

```bash
createdb -h 127.0.0.1 -U cm cm_test          # یک‌بار
DATABASE_URL=postgresql+psycopg://cm:cm@127.0.0.1:5432/cm_test python -m pytest
```

پوشش تست شامل: reconciliation موجودی، FIFO چندلاتی و سود/زیان دوارزی، carry-over انتقال،
مانده‌ی بدهی (بدون دابل‌کانت بهره)، ارزش خالص، idempotency اسنپ‌شات، progress اهداف،
XIRR/TWR (با تست ضدّدابل‌کانت income)، تورم/hurdle، تخصیص و پیش‌بینی. (**۱۰۲ تست**)

## OpenAPI (قرارداد برای فرانت)

`openapi.json` در ریشه‌ی ریپو، از روی اپ تولید می‌شود و **منبع حقیقت قرارداد** است:

```bash
python scripts/export_openapi.py
```

پس از هر تغییر در endpointها این فایل را دوباره تولید کن و در ریپوی فرانت کپی کن
(فرانت با `npm run gen:api` از آن کلاینت و schemaهای اعتبارسنجی می‌سازد).

## ساختار پروژه

```
app/
  api/        # routerها (auth, accounts, assets, prices, transactions, holdings,
              #            liabilities, goals, snapshots, settings, reports)
  models/     # SQLAlchemy (user, account, asset, transaction(_leg), price, lot,
              #             liability(_event), portfolio_snapshot, goal, assumptions, ...)
  schemas/    # Pydantic (ورودی/خروجی API)
  services/   # منطق مالی: ledger, valuation, lots, holdings, pnl, net_worth,
              #            liabilities, snapshots, goals, performance, inflation,
              #            allocation, projection
  jobs/       # job دوره‌ی اسنپ‌شات
  core/       # config, db, security, deps, errors, pagination
migrations/   # Alembic
tests/        # pytest
scripts/      # export_openapi.py
```

## قواعد کلیدی

- **پول:** هر مقدار پولی/مقدار دارایی `NUMERIC(38,18)` است و در API به‌صورت **رشته** سریالایز می‌شود (بدون افت دقت). هرگز float.
- **مشتق‌شده:** موجودی، سود/زیان، ارزش خالص و progress هرگز ذخیره‌ی دستی نمی‌شوند؛ از تراکنش‌ها/قیمت‌ها بازتولید و reconcile می‌شوند.
- **دوارزی:** هر گزارش در IRR و USD؛ نرخ USD/IRR یک رکورد `price` است؛ تبدیل با نزدیک‌ترین قیمت `as_of <= تاریخ`.
- **scope کاربر:** هر query با `user_id` محدود است؛ دارایی‌های `user_id IS NULL` سیستمی و مشترک‌اند.
- **حذف نرم و audit:** رکورد مالی واقعاً حذف نمی‌شود (`deleted_at`)؛ هر create/update/reverse/delete در `audit_log` ثبت می‌شود.
- **تاریخ:** ذخیره UTC، خروجی ISO-8601.
- **خطا:** قالب یکنواخت `{"error": {"code", "message", "details?}}`. صفحه‌بندی: `?page=&page_size=` → `{items, total, page, page_size}`.

## job اسنپ‌شات روزانه

با `ENABLE_SCHEDULER=true` یک thread پس‌زمینه روزی یک‌بار (زمان UTC قابل‌تنظیم) برای همه‌ی کاربران اسنپ‌شات می‌سازد.
برای ورود داده‌ی تاریخی یا بازسازی، از endpoint عملیاتی استفاده کن:

```
POST /api/v1/snapshots/rebuild   { "from": "2026-01-01", "to": "2026-06-01" }
```

این عملیات idempotent است (upsert روی (user, as_of)).
