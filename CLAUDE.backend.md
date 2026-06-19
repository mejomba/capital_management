# CLAUDE.md — ریپو بک‌اند (Wealth Manager Backend)

این فایل قواعد قطعی ریپو بک‌اند است. قبل از هر تغییر بخوان و رعایت کن.
اسناد مرجع کنار همین فایل: `PRD.md`، `GLOSSARY.md`، `DATA_MODEL.md`، `API_CONTRACT.md`، `ROADMAP.md`.

---

## ۱. نقش این ریپو
بک‌اند، **منبع حقیقت (source of truth)** کل سیستم است: مدل داده، منطق مالی، و قرارداد API.
فرانت فقط مصرف‌کننده‌ی این API است. هر منطق محاسباتی این‌جا انجام می‌شود، نه در فرانت.

## ۲. استک
- Python 3.12+، **FastAPI**، **PostgreSQL**، **SQLAlchemy 2.x**، **Alembic** (migration)، **Pydantic v2**.
- کارهای پس‌زمینه (اسنپ‌شات روزانه‌ی پرتفو): APScheduler یا cron ساده.
- تست: **pytest**. مدیریت محیط: docker-compose برای DB.

## ۳. اصل طلایی
> هیچ مقدار محاسبه‌شده‌ای ذخیره‌ی دستی نمی‌شود. موجودی (holding)، سود/زیان و ارزش خالص
> همگی **مشتق‌شده از `transactions`** هستند و باید قابل بازتولید و قابل تطبیق (reconcilable) باشند.
اگر چیزی را cache کردی، صریحاً نشانه‌گذاری کن و راهی برای بازساخت از تراکنش‌ها بگذار.

## ۴. قواعد پول و عدد (بدون استثنا)
- همه‌ی مقادیر پولی و مقدار دارایی: **`Decimal`** در پایتون، **`NUMERIC(38,18)`** در DB. **هرگز float**.
- در API، اعداد پولی به‌صورت **رشته** سریالایز شوند تا دقت از بین نرود (Pydantic: `Decimal` → `str`).
- گرد کردن فقط در صورت درخواست صریح؛ محاسبات میانی بدون گرد کردن.

## ۵. ارز پایه دوگانه (IRR + USD)
- هر مبلغ همراه ارز است. نقدینگی = موجودی دارایی `fiat` (IRR/USD) در یک حساب.
- نرخ USD/IRR یک سری زمانی در همان جدول `price` است (نه جدول جدا).
- تبدیل = نزدیک‌ترین قیمت با `as_of <= تاریخ هدف`. هر گزارش باید در هر دو ارز قابل ارائه باشد.

## ۶. FIFO و سود/زیان
- هر پایه‌ی افزایشیِ دارایی غیرنقدی یک `lot` می‌سازد؛ قیمت تمام‌شده‌ی لات **هم به IRR و هم به USD**
  در لحظه‌ی خرید snapshot می‌شود (تا گزارش دلاری پایدار بماند).
- فروش، لات‌ها را به‌ترتیب `acquired_at` صعودی مصرف می‌کند و `lot_consumption` با realized P&L می‌سازد.
- الگوریتم cost-basis را به‌صورت **strategy قابل‌تعویض** پیاده کن (FIFO الان، WAC/LIFO بعداً).
- فروش بیش از موجودی → خطای اعتبارسنجی (۴۲۲)، نه مقدار منفی.

## ۷. تفکیک انواع رویداد
چهار رویداد را هرگز قاطی نکن (تعریف کامل در `GLOSSARY.md`):
`deposit`/`withdrawal` (جریان بیرونی، بدون P&L) · `trade` (دو پایه، تولید cost basis) ·
`transfer` (هم‌دارایی، بدون P&L) · `income` (سود/اجاره/استیکینگ).
بدهی‌ها: `liability_disbursement`/`repayment`/`interest`.

## ۸. چندکاربره و امنیت
- `user_id` روی همه‌ی جداول کاربری. هیچ query بدون scope کاربر اجرا نشود.
- یک dependency مشترک برای استخراج کاربر از JWT + بررسی مالکیت در هر endpoint.
- رمز با argon2/bcrypt. JWT با انقضا. هیچ داده‌ی کاربر دیگری نشت نکند.

## ۹. تغییرناپذیری، حذف نرم، Audit
- تراکنش immutable است؛ «ویرایش» = `reverse` (ثبت معکوس) + نسخه‌ی جدید.
- هیچ رکورد مالی واقعاً DELETE نمی‌شود → `deleted_at`.
- هر create/update/reverse/delete در `audit_log` با diff ثبت شود.

## ۱۰. تاریخ
- ذخیره‌سازی همیشه **UTC**. تبدیل و گزارش شمسی کارِ فرانت است؛ بک‌اند فقط ISO می‌دهد.
- پارامترهای بازه‌ی گزارش (`from`/`to`) ISO هستند.

## ۱۱. قرارداد API (مهم برای جداسازی از فرانت)
- `API_CONTRACT.md` سند طراحی است؛ **OpenAPI تولیدشده‌ی FastAPI منبع حقیقت اجرایی** است.
- هر تغییر endpoint باید هم‌زمان در کد، در `API_CONTRACT.md`، و در schemaها منعکس شود.
- قالب خطای یکنواخت: `{error: {code, message, details?}}`. صفحه‌بندی استاندارد `{items,total,page,page_size}`.
- یک `openapi.json` در ریشه export کن تا فرانت ازش کلاینت تایپ‌دار بسازد.

## ۱۲. تست و کیفیت
- تست واحد برای هر منطق مالی: FIFO چندلاتی، فروش جزئی، realized/unrealized، تبدیل دوارزی، XIRR، TWR.
- **تست‌های reconciliation** (در CI سبز بمانند):
  «جمع پایه‌های هر دارایی = موجودی محاسبه‌شده» و «ارزش خالص = جمع ارزش دارایی‌ها − بدهی‌ها».
- هیچ milestone تا سبزشدن این تست‌ها تمام‌شده فرض نشود.

## ۱۳. ساختار ریپو
```
/app
  /api          # routerها (auth, accounts, assets, prices, transactions, holdings, liabilities, goals, reports, settings)
  /models       # SQLAlchemy
  /schemas      # Pydantic
  /services     # منطق مالی: ledger, valuation, fifo, performance, projection
  /core         # config, security, db, deps
  /jobs         # snapshot دوره‌ای
/migrations     # Alembic
/tests
docker-compose.yml
openapi.json
```

## ۱۴. روال کار با Claude Code
ترتیب از `ROADMAP.md` (M1→M5 مال این ریپو). در هر مرحله **اول پلن و لیست فایل‌ها**، بعد کد، بعد تست.
لایه‌ی منطق مالی را در `/services` نگه دار و آن را مستقل از FastAPI و قابل‌تست واحد بساز.
