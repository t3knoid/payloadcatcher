from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SafeError(BaseModel):
    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Safe human-readable error message.")
    details: dict[str, Any] | None = Field(default=None, description="Optional safe error metadata.")


class SafeErrorResponse(BaseModel):
    error: SafeError
    request_id: str = Field(description="Request correlation identifier.")