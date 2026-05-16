from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

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