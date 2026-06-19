"""Uniform error envelope: {"error": {"code", "message", "details?}}."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain error rendered with the uniform error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


# Common shortcuts ----------------------------------------------------------

def not_found(message: str = "Resource not found", details: Any | None = None) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "not_found", message, details)


def unauthorized(message: str = "Not authenticated", details: Any | None = None) -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message, details)


def forbidden(message: str = "Forbidden", details: Any | None = None) -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "forbidden", message, details)


def conflict(message: str = "Conflict", details: Any | None = None) -> AppError:
    return AppError(status.HTTP_409_CONFLICT, "conflict", message, details)


def unprocessable(message: str = "Unprocessable entity", details: Any | None = None) -> AppError:
    return AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "unprocessable_entity", message, details)


# Rendering -----------------------------------------------------------------

def _envelope(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            status.HTTP_401_UNAUTHORIZED: "unauthorized",
            status.HTTP_403_FORBIDDEN: "forbidden",
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_409_CONFLICT: "conflict",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "unprocessable_entity",
                "Validation failed",
                jsonable_details(exc.errors()),
            ),
        )


def jsonable_details(errors: Any) -> Any:
    """Make validation error details JSON-serialisable (drop exception objects)."""
    cleaned = []
    for err in errors:
        cleaned.append(
            {k: v for k, v in err.items() if k != "ctx" or _is_jsonable(v)}
        )
    return cleaned


def _is_jsonable(value: Any) -> bool:
    import json

    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False
