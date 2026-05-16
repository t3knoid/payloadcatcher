from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


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


class InboxViewerQuery(BaseModel):
    q: Annotated[str | None, StringConstraints(strip_whitespace=True)] = Field(
        default=None,
        description="Optional search text for request ID, method, source IP, or payload preview content.",
    )
    cursor: str | None = Field(default=None, description="Opaque pagination cursor from the previous response.")
    limit: int = Field(default=50, description="Page size for inbox event summaries. Default 50, max 100.")


class InboxEventSummary(BaseModel):
    request_id: str = Field(description="Server-generated request identifier for the stored event.")
    received_at: datetime = Field(description="UTC timestamp when the event was received.")
    method: str = Field(description="HTTP method used for the webhook request.")
    content_type: str | None = Field(description="Normalized content type for the captured payload.")
    payload_yaml: str = Field(description="Safe YAML or text preview for the event, truncated for public listing use.")
    source_ip_masked: str = Field(description="Redacted network identifier for public bearer-link viewing.")


class InboxEventDetailResponse(BaseModel):
    request_id: str = Field(description="Server-generated request identifier for the stored event.")
    received_at: datetime = Field(description="UTC timestamp when the event was received.")
    method: str = Field(description="HTTP method used for the webhook request.")
    content_type: str | None = Field(description="Normalized content type for the captured payload.")
    headers: dict[str, str] = Field(description="Sanitized request headers captured for the event.")
    payload_yaml: str = Field(description="Full safe YAML or text rendering stored for this event.")
    source_ip_masked: str = Field(description="Redacted network identifier for public bearer-link viewing.")
    payload_size_bytes: int = Field(description="Stored raw payload size in bytes.")


class InboxViewerMetadata(BaseModel):
    inbox_issued_at: datetime = Field(description="UTC timestamp when the inbox was issued.")
    expires_at: datetime = Field(description="UTC timestamp when the inbox expires.")
    capture_count: int = Field(description="Total number of captured events currently associated with the inbox.")


class InboxViewerResponse(BaseModel):
    hook_url: str = Field(description="Canonical hook URL for the requested inbox.")
    events: list[InboxEventSummary] = Field(description="Newest-first page of captured event summaries.")
    next_token: str | None = Field(description="Opaque cursor token for the next page, or null when exhausted.")
    metadata: InboxViewerMetadata