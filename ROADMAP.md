# ROADMAP — مرحله‌بندی ساخت

به Claude Code **یک milestone در هر بار** بده. در هر مرحله اول پلن و لیست فایل‌ها، بعد کد، بعد تست.
مرحله تا سبزشدن تست‌های reconciliation تمام‌شده فرض نشود.

## ساختار مخزن
```
/wealth-manager
  /backend        # FastAPI + PostgreSQL + SQLAlchemy + Alembic
  /frontend       # React + TS (Vite) + React Query + Recharts
  CLAUDE.md  PRD.md  GLOSSARY.md  DATA_MODEL.md  API_CONTRACT.md  ROADMAP.md
  docker-compose.yml
```

## M1 — پایه‌ی بک‌اند و احراز هویت
- راه‌اندازی FastAPI، اتصال PostgreSQL، Alembic، Pydantic settings، docker-compose.
- مدل‌ها و migration برای: user, account, asset (+ seed دارایی‌های سیستمی: IRR, USD, BTC, ETH, XAU…).
- ثبت‌نام/ورود/JWT، middleware مالکیت.
- **خروجی:** CRUD حساب و دارایی + تست auth. OpenAPI تولید شود.

## M2 — دفتر تراکنش و موجودی مشتق‌شده
- transaction + transaction_leg با اعتبارسنجی هر نوع (deposit/withdrawal/trade/transfer/income/fee/expense).
- محاسبه‌ی موجودی (account, asset) از جمع پایه‌ها.
- باطل‌سازی (reverse) + soft delete + audit_log.
- **تست reconciliation:** «جمع پایه‌ها = موجودی». فروش بیش از موجودی رد شود.
- **خروجی:** endpointهای transactions و holdings.

## M3 — قیمت، FIFO و سود/زیان (دوارزی)
- price (ورود دستی) + نرخ FX به‌صورت price.
- ساخت lot هنگام خرید؛ مصرف FIFO هنگام فروش؛ lot_consumption.
- realized P&L و unrealized P&L در IRR و USD (با snapshot نرخ ارز تاریخ خرید).
- strategy قابل‌تعویض برای cost-basis.
- **تست:** سناریوهای FIFO چندلاتی، فروش جزئی، تبدیل دوارزی.
- **خروجی:** holdings با ارزش‌گذاری، گزارش pnl.

## M4 — بدهی، اهداف، اسنپ‌شات و ارزش خالص
- liability + liability_event؛ مانده‌ی مشتق‌شده.
- ارزش خالص = دارایی − بدهی، در هر دو ارز.
- job دوره‌ای ساخت portfolio_snapshot.
- goal + محاسبه‌ی progress.
- **خروجی:** reports/net-worth، liabilities، goals.

## M5 — تحلیل، تورم و پیش‌بینی
- assumptions + inflation_rate.
- بازدهی: xirr، twr، nominal، real، usd-based.
- allocation فعلی/هدف/drift + پیشنهاد بازتعادل.
- جدول inflation-comparison.
- projection سه‌سناریویی.
- **خروجی:** reports/performance، allocation، inflation-comparison، projection. OpenAPI نهایی.

## M6 — فرانت‌اند
- اسکلت React + TS، React Query، احراز هویت، RTL/فارسی، تقویم شمسی.
- صفحات: داشبورد (ارزش خالص + ترکیب)، حساب‌ها/دارایی‌ها، ثبت تراکنش (فرم‌های مخصوص هر نوع)،
  قیمت‌ها، بدهی‌ها، اهداف، گزارش‌ها (بازدهی، تورم، پیش‌بینی).
- نمودارها با Recharts؛ سوییچ ارز IRR/USD سراسری.
- **خروجی:** فرانت کامل روی OpenAPI.

## فازهای بعدی (خارج از فاز اول)
- اتصال خودکار API قیمت‌ها، ورود CSV، هشدارها، اشتراک‌گذاری پرتفو، تحلیل ریسک.
