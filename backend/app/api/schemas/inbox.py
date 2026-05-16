from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProvisionInboxQuery(BaseModel):
    timezone: str | None = Field(
        default=None,
        description="Optional browser-provided timezone hint for visit metadata capture.",
    )


class ProvisionInboxResponse(BaseModel):
    clsid: str = Field(description="Lowercase UUIDv4 inbox identifier.")
    callback_url: str = Field(description="Provider-agnostic webhook callback URL for this inbox.")
    viewer_url: str = Field(description="Viewer URL for the provisioned inbox.")
    expires_at: datetime = Field(description="UTC timestamp when the current callback expires.")
    new_session: bool = Field(description="Whether the request created a new active inbox for this session.")