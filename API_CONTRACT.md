# API_CONTRACT — قرارداد REST

پیشوند پایه: `/api/v1`. احراز هویت: `Authorization: Bearer <jwt>`.
همه‌ی endpointها scope به کاربر احرازشده. مبالغ به‌صورت رشته‌ی Decimal رد و بدل شوند (نه float).
این فایل منبع حقیقت است؛ OpenAPI باید با آن هم‌خوان بماند.

## Auth
- `POST /auth/register` → `{email, password, display_name}` → `{user, token}`
- `POST /auth/login` → `{email, password}` → `{token}`
- `GET  /auth/me` → پروفایل کاربر جاری

## Accounts
- `GET    /accounts`
- `POST   /accounts` → `{name, type, currency_hint?, note?}`
- `GET    /accounts/{id}`
- `PATCH  /accounts/{id}`
- `DELETE /accounts/{id}` (soft delete)

## Assets
- `GET    /assets?class=&q=` (شامل سیستمی + سفارشی کاربر)
- `POST   /assets` → `{symbol, name, asset_class, unit, quote_currency}`
- `GET    /assets/{id}`
- `PATCH  /assets/{id}`

## Prices (ورود دستی)
- `GET    /prices?asset_id=&from=&to=`
- `POST   /prices` → `{asset_id, quote_currency, price, as_of}`
- `POST   /prices/bulk` → آرایه‌ای از قیمت‌ها (ورود گروهی دستی)
- `GET    /fx?from=USD&to=IRR&as_of=` → نرخ ارز (مشتق از prices)

## Transactions
- `GET    /transactions?type=&account_id=&asset_id=&from=&to=&tag=&page=`
- `POST   /transactions` → بدنه بسته به نوع (نمونه‌ها پایین)
- `GET    /transactions/{id}`
- `POST   /transactions/{id}/reverse` (باطل‌سازی؛ تراکنش immutable است)
- `DELETE /transactions/{id}` (soft delete + audit)

### نمونه بدنه‌ها
```jsonc
// deposit
{ "type":"deposit", "occurred_at":"...", "account_id":"...", "asset_id":"...", "quantity":"100000000", "note":"" }

// trade (خرید BTC با تومان)
{ "type":"trade", "occurred_at":"...",
  "legs":[
    {"account_id":"acc1","asset_id":"IRR","quantity":"-500000000","unit_price":"1","price_currency":"IRR"},
    {"account_id":"acc1","asset_id":"BTC","quantity":"0.01","unit_price":"50000000000","price_currency":"IRR"}
  ],
  "fee":"100000","fee_currency":"IRR" }

// transfer (انتقال BTC بین دو حساب)
{ "type":"transfer", "occurred_at":"...",
  "legs":[
    {"account_id":"exchange","asset_id":"BTC","quantity":"-0.01"},
    {"account_id":"coldwallet","asset_id":"BTC","quantity":"0.0099"}
  ],
  "fee":"0.0001","fee_currency":"BTC" }
```

## Holdings (فقط خواندنی، مشتق‌شده)
- `GET /holdings?as_of=` → موجودی هر (account, asset) + ارزش IRR/USD + unrealized P&L
- `GET /holdings/by-asset?as_of=`
- `GET /holdings/by-class?as_of=`

## Liabilities
- `GET    /liabilities`
- `POST   /liabilities` → `{name, type, principal, currency, interest_rate, start_date, term_months, schedule?}`
- `GET    /liabilities/{id}` (شامل مانده‌ی مشتق‌شده)
- `POST   /liabilities/{id}/events` → `{type, amount, currency, occurred_at, principal_component?, interest_component?}`

## Goals
- `GET    /goals`
- `POST   /goals` → `{type, title, target_value?, currency?, target_allocation?, target_date}`
- `GET    /goals/{id}` (شامل progress مشتق‌شده)
- `PATCH  /goals/{id}`

## Snapshots (پرتفو، مشتق‌شده)
- `GET  /snapshots?from=&to=` → اسنپ‌شات‌های روزانه‌ی کاربر (ارزش خالص دوارزی + breakdown).
- `POST /snapshots/rebuild` → `{from, to}` → بازسازی/backfill اسنپ‌شات‌ها در بازه (idempotent، upsert روی (user, as_of)). خروجی `{created, from, to}`. برای ورود داده‌ی تاریخی استفاده می‌شود. اسنپ‌شات روزانه به‌صورت job هم ساخته می‌شود.

## Reports
- `GET /reports/net-worth?from=&to=&currency=both` → سری زمانی از snapshotها
- `GET /reports/allocation?as_of=&currency=` → فعلی + هدف + drift + پیشنهاد بازتعادل
- `GET /reports/pnl?from=&to=&group_by=class|account|asset` → realized + unrealized
- `GET /reports/performance?from=&to=` → `{xirr, twr, nominal, real, usd_based}`
- `GET /reports/inflation-comparison?from=&to=` → جدول واقعیت/تورم/hurdle
- `GET /reports/projection?horizon_months=&monthly_contribution=&scenario=` → سه سناریو

## Settings / Assumptions
- `GET   /assumptions`
- `PUT   /assumptions` → `{display_currency, hurdle_mode, hurdle_fixed_rate, growth_assumptions}`
- `GET   /inflation` , `POST /inflation` → سری تورم

## قراردادهای عمومی
- خطاها: قالب یکنواخت `{error: {code, message, details?}}`.
- صفحه‌بندی: `?page=&page_size=` با `{items, total, page, page_size}`.
- تاریخ‌ها در API میلادی/ISO؛ تبدیل شمسی در فرانت.
- اعتبارسنجی: فروش بیش از موجودی، پایه‌های نامتوازن، و قیمت گم‌شده باید ۴۲۲ بدهند.
