from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_context


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details
        self.headers = headers or {}


def build_error_content(
    error_code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    request_id_value = request_id or request_id_context.get()
    error: dict[str, Any] = {
        "code": error_code,
        "message": message,
    }
    if details is not None:
        error["details"] = details
    return {
        "error": error,
        "request_id": request_id_value,
    }


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_content(exc.error_code, exc.message, details=exc.details),
        headers=exc.headers,
    )


def _status_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        413: "payload_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        503: "service_unavailable",
    }.get(status_code, "request_failed")


def _status_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _build_retry_details(headers: dict[str, str] | None, status_code: int) -> dict[str, Any] | None:
    if status_code not in {429, 503} or not headers:
        return None

    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after is None:
        return None

    try:
        return {"retry_after_seconds": int(retry_after)}
    except ValueError:
        return None


def _sanitize_validation_errors(exc: RequestValidationError) -> dict[str, Any]:
    return {
        "errors": [
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", "Validation error"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
    }


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    headers = dict(exc.headers or {})
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else _status_message(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_content(
            _status_error_code(exc.status_code),
            message,
            details=_build_retry_details(headers, exc.status_code),
        ),
        headers=headers,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=build_error_content(
            "validation_error",
            "Request validation failed",
            details=_sanitize_validation_errors(exc),
        ),
    )