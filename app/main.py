from fastapi import FastAPI

from app.api import accounts, assets, auth, holdings, prices, reports, transactions
from app.core.config import settings
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Wealth Manager backend — source of truth for the API contract.",
    )

    register_exception_handlers(app)

    api_prefix = settings.API_V1_PREFIX
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(accounts.router, prefix=api_prefix)
    app.include_router(assets.router, prefix=api_prefix)
    app.include_router(transactions.router, prefix=api_prefix)
    app.include_router(holdings.router, prefix=api_prefix)
    app.include_router(prices.router, prefix=api_prefix)
    app.include_router(reports.router, prefix=api_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
