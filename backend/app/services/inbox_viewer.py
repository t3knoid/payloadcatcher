from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
import ipaddress
import json
import uuid

from fastapi import Depends, Request
from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas.inbox import (
    InboxEventDetailResponse,
    InboxEventSummary,
    InboxViewerMetadata,
    InboxViewerQuery,
    InboxViewerResponse,
)
from app.core.config import Settings, get_settings
from app.infrastructure.rate_limit import InMemoryRateLimiter, get_hook_rate_limiter
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session


@dataclass(slots=True)
class InboxCursor:
    received_at: datetime
    request_id: str


class InboxViewerService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        rate_limiter: InMemoryRateLimiter | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.rate_limiter = rate_limiter

    def get_inbox_view(self, clsid: str, query: InboxViewerQuery, request: Request) -> InboxViewerResponse:
        limit = self.validate_limit(query.limit)
        cursor = self.decode_cursor(query.cursor)
        inbox = self._get_active_inbox(clsid, request, rate_limit_scope="viewer")

        matched_events = self._load_events(inbox.id, query.q, cursor, limit)
        next_token = None
        if len(matched_events) > limit:
            next_token = self.encode_cursor(matched_events[limit - 1])
            matched_events = matched_events[:limit]

        capture_count = self.session.scalar(
            select(func.count()).select_from(WebhookEvent).where(WebhookEvent.inbox_id == inbox.id)
        )

        return InboxViewerResponse(
            hook_url=self._build_hook_url(inbox.clsid),
            events=[self._build_event_summary(event) for event in matched_events],
            next_token=next_token,
            metadata=InboxViewerMetadata(
                inbox_issued_at=inbox.issued_at,
                expires_at=inbox.expires_at,
                capture_count=capture_count or 0,
            ),
        )

    def get_inbox_event_detail(self, clsid: str, request_id: str, request: Request) -> InboxEventDetailResponse:
        inbox = self._get_active_inbox(clsid, request, rate_limit_scope="viewer-detail")
        event = self.session.scalar(
            select(WebhookEvent).where(
                WebhookEvent.inbox_id == inbox.id,
                WebhookEvent.request_id == request_id,
            )
        )
        if event is None:
            raise ApiError(404, "event_not_found", "Event not found for inbox")

        return InboxEventDetailResponse(
            request_id=event.request_id,
            received_at=self._response_datetime(event.received_at),
            method=event.method,
            content_type=event.content_type,
            headers=self._serialize_headers(event.headers_json),
            payload_yaml=event.payload_yaml,
            source_ip_masked=self.mask_source_ip(event.source_ip),
            payload_size_bytes=event.payload_size_bytes,
        )

    def validate_clsid(self, clsid: str) -> str:
        try:
            parsed = uuid.UUID(clsid)
        except ValueError as exc:
            raise ApiError(400, "invalid_clsid", "clsid must be a lowercase UUIDv4") from exc

        if parsed.version != 4 or str(parsed) != clsid:
            raise ApiError(400, "invalid_clsid", "clsid must be a lowercase UUIDv4")
        return clsid

    def validate_limit(self, limit: int) -> int:
        if limit < 1 or limit > 100:
            raise ApiError(400, "invalid_limit", "limit must be between 1 and 100")
        return limit

    def normalize_source_ip(self, client_host: str | None, forwarded_for: str | None) -> str:
        if client_host and client_host in self.settings.trusted_proxies and forwarded_for:
            first_forwarded = forwarded_for.split(",", maxsplit=1)[0].strip()
            if self._is_valid_ip_address(first_forwarded):
                return first_forwarded
        return client_host or "unknown"

    def enforce_rate_limit(self, source_ip: str, scope: str) -> None:
        if self.rate_limiter is None:
            return

        retry_after = self.rate_limiter.check_and_consume(f"{scope}:{source_ip}")
        if retry_after is None:
            return

        raise ApiError(
            429,
            "rate_limited",
            "Too many requests",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    def decode_cursor(self, cursor: str | None) -> InboxCursor | None:
        if cursor is None:
            return None

        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            return InboxCursor(
                received_at=datetime.fromisoformat(payload["received_at"]),
                request_id=payload["request_id"],
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_cursor", "cursor is invalid") from exc

    def encode_cursor(self, event: WebhookEvent) -> str:
        payload = json.dumps(
            {
                "received_at": self._cursor_datetime(event.received_at).isoformat(),
                "request_id": event.request_id,
            },
            separators=(",", ":"),
        )
        return urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")

    def mask_source_ip(self, source_ip: str) -> str:
        try:
            parsed = ipaddress.ip_address(source_ip)
        except ValueError:
            return "unknown"

        if isinstance(parsed, ipaddress.IPv4Address):
            return str(ipaddress.ip_network(f"{parsed}/24", strict=False))
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False))

    def truncate_payload_yaml(self, payload_yaml: str) -> str:
        max_chars = self.settings.viewer_payload_preview_chars
        if len(payload_yaml) <= max_chars:
            return payload_yaml
        return payload_yaml[: max_chars - 3] + "..."

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def _get_active_inbox(self, clsid: str, request: Request, rate_limit_scope: str) -> Inbox:
        normalized_clsid = self.validate_clsid(clsid)
        source_ip = self.normalize_source_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
        )
        self.enforce_rate_limit(source_ip, rate_limit_scope)

        inbox = self.session.scalar(
            select(Inbox).where(
                Inbox.clsid == normalized_clsid,
                Inbox.expires_at > self.utc_now(),
            )
        )
        if inbox is None:
            raise ApiError(404, "inbox_not_found", "Inbox not found or expired")
        return inbox

    def _load_events(
        self,
        inbox_id: uuid.UUID,
        search_text: str | None,
        cursor: InboxCursor | None,
        limit: int,
    ) -> list[WebhookEvent]:
        filters = [WebhookEvent.inbox_id == inbox_id]
        if search_text:
            filters.append(self._build_search_filter(search_text))
        if cursor is not None:
            filters.append(
                or_(
                    WebhookEvent.received_at < cursor.received_at,
                    and_(
                        WebhookEvent.received_at == cursor.received_at,
                        WebhookEvent.request_id < cursor.request_id,
                    ),
                )
            )

        statement = (
            select(WebhookEvent)
            .where(*filters)
            .order_by(WebhookEvent.received_at.desc(), WebhookEvent.request_id.desc())
            .limit(limit + 1)
        )
        return list(self.session.scalars(statement))

    def _build_search_filter(self, search_text: str):
        normalized = f"%{self._escape_like_pattern(search_text.lower())}%"
        preview_text = func.lower(self._preview_expression())
        return or_(
            func.lower(WebhookEvent.request_id).like(normalized, escape="\\"),
            func.lower(WebhookEvent.method).like(normalized, escape="\\"),
            func.lower(WebhookEvent.source_ip).like(normalized, escape="\\"),
            preview_text.like(normalized, escape="\\"),
        )

    def _escape_like_pattern(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _build_event_summary(self, event: WebhookEvent) -> InboxEventSummary:
        return InboxEventSummary(
            request_id=event.request_id,
            received_at=self._response_datetime(event.received_at),
            method=event.method,
            content_type=event.content_type,
            payload_yaml=self.truncate_payload_yaml(event.payload_yaml),
            source_ip_masked=self.mask_source_ip(event.source_ip),
        )

    def _build_hook_url(self, clsid: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/hook/{clsid}"

    def _serialize_headers(self, headers: object) -> dict[str, str]:
        if not isinstance(headers, dict):
            return {}

        serialized: dict[str, str] = {}
        for key, value in headers.items():
            serialized[str(key)] = str(value)
        return serialized

    def _is_valid_ip_address(self, value: str) -> bool:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    def _cursor_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _response_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _preview_expression(self):
        max_chars = self.settings.viewer_payload_preview_chars
        truncated_text = cast(func.substr(WebhookEvent.payload_yaml, 1, max_chars - 3), String) + literal("...")
        return case(
            (func.length(WebhookEvent.payload_yaml) <= max_chars, WebhookEvent.payload_yaml),
            else_=truncated_text,
        )


def get_inbox_viewer_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    rate_limiter: InMemoryRateLimiter = Depends(get_hook_rate_limiter),
) -> InboxViewerService:
    return InboxViewerService(session=session, settings=settings, rate_limiter=rate_limiter)