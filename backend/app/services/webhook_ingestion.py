from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import ipaddress
import json
from json import JSONDecodeError
import logging
import re
import uuid
from urllib.parse import parse_qs

import yaml
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.infrastructure.rate_limit import InMemoryRateLimiter, get_hook_rate_limiter
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session


CONTENT_TYPE_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class PreparedWebhookIngestion:
    inbox_id: uuid.UUID
    clsid: str
    request_id: str
    received_at: datetime
    source_ip: str
    method: str
    content_type: str | None
    payload_raw: bytes
    payload_encoding: str | None
    headers_json: dict[str, str]


class WebhookIngestionService:
    def __init__(
        self,
        session: Session | None,
        session_factory: sessionmaker[Session] | None,
        settings: Settings,
        rate_limiter: InMemoryRateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.settings = settings
        self.rate_limiter = rate_limiter
        self.clock = clock or utc_now
        self.logger = logging.getLogger("payloadcatcher.hook")

    def prepare_ingestion(self, clsid: str, request: Request, payload_raw: bytes) -> PreparedWebhookIngestion:
        if self.session is None:
            raise RuntimeError("Session is required to prepare webhook ingestion")

        normalized_clsid = self.validate_clsid(clsid)
        source_ip = self.normalize_source_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
        )
        self.enforce_rate_limit(source_ip)
        content_type = self.normalize_content_type(request.headers.get("content-type"))
        self.validate_payload_size(payload_raw)

        inbox = self.session.scalar(
            select(Inbox).where(
                Inbox.clsid == normalized_clsid,
                Inbox.expires_at > self.clock(),
            )
        )
        if inbox is None:
            raise ApiError(404, "inbox_not_found", "Inbox not found or expired")

        return PreparedWebhookIngestion(
            inbox_id=inbox.id,
            clsid=normalized_clsid,
            request_id=uuid.uuid4().hex,
            received_at=self.clock(),
            source_ip=source_ip,
            method=request.method,
            content_type=content_type,
            payload_raw=payload_raw,
            payload_encoding=request.headers.get("content-encoding"),
            headers_json=self.sanitized_headers(request),
        )

    def persist_ingestion(self, prepared: PreparedWebhookIngestion) -> None:
        if self.session_factory is None:
            raise RuntimeError("Session factory is required to persist webhook ingestion")

        with self.session_factory() as session:
            try:
                session.add(
                    WebhookEvent(
                        inbox_id=prepared.inbox_id,
                        request_id=prepared.request_id,
                        received_at=prepared.received_at,
                        method=prepared.method,
                        content_type=prepared.content_type,
                        headers_json=prepared.headers_json,
                        payload_raw=prepared.payload_raw,
                        payload_size_bytes=len(prepared.payload_raw),
                        payload_encoding=prepared.payload_encoding,
                        payload_yaml=self.render_payload_yaml(prepared.payload_raw, prepared.content_type),
                        source_ip=prepared.source_ip,
                        dedup_key=None,
                        is_duplicate=False,
                    )
                )
                session.commit()
            except Exception:
                session.rollback()
                self.logger.exception(
                    "Webhook persistence failed for clsid=%s request_id=%s",
                    prepared.clsid,
                    prepared.request_id,
                )
                raise

        self.logger.info(
            "Webhook accepted for clsid=%s request_id=%s content_type=%s payload_size_bytes=%s",
            prepared.clsid,
            prepared.request_id,
            prepared.content_type or "unknown",
            len(prepared.payload_raw),
        )

    def validate_clsid(self, clsid: str) -> str:
        try:
            parsed = uuid.UUID(clsid)
        except ValueError as exc:
            raise ApiError(400, "invalid_clsid", "clsid must be a lowercase UUIDv4") from exc

        if parsed.version != 4 or str(parsed) != clsid:
            raise ApiError(400, "invalid_clsid", "clsid must be a lowercase UUIDv4")
        return clsid

    def validate_payload_size(self, payload_raw: bytes) -> None:
        if len(payload_raw) > self.settings.hook_payload_max_bytes:
            raise ApiError(
                413,
                "payload_too_large",
                "Payload exceeds configured size limit",
                details={"max_bytes": self.settings.hook_payload_max_bytes},
            )

    def enforce_rate_limit(self, source_ip: str) -> None:
        if self.rate_limiter is None:
            return

        retry_after = self.rate_limiter.check_and_consume(source_ip)
        if retry_after is None:
            return

        raise ApiError(
            429,
            "rate_limited",
            "Too many requests",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    def normalize_content_type(self, content_type: str | None) -> str | None:
        if content_type is None:
            return None

        media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
        if not media_type:
            return None
        if not CONTENT_TYPE_PATTERN.match(media_type):
            raise ApiError(415, "unsupported_media_type", "Content-Type header is invalid")
        return media_type

    def normalized_form_payload(self, payload_text: str) -> dict[str, str | list[str]]:
        parsed = parse_qs(payload_text, keep_blank_values=True)
        normalized: dict[str, str | list[str]] = {}
        for key, values in parsed.items():
            normalized[key] = values[0] if len(values) == 1 else values
        return normalized

    def render_payload_yaml(self, payload_raw: bytes, content_type: str | None) -> str:
        if self._is_json_media_type(content_type):
            try:
                parsed_json = json.loads(payload_raw.decode("utf-8"))
            except (UnicodeDecodeError, JSONDecodeError):
                self.logger.warning(
                    "Malformed JSON payload fell back to text or binary preview"
                )
                return self._render_text_or_binary_preview(payload_raw, content_type)
            return yaml.safe_dump(parsed_json, sort_keys=False, allow_unicode=True)

        if content_type == "application/x-www-form-urlencoded":
            try:
                parsed_form = self.normalized_form_payload(payload_raw.decode("utf-8"))
            except UnicodeDecodeError:
                self.logger.warning(
                    "Malformed form payload fell back to binary preview"
                )
                return self._render_binary_preview(payload_raw, content_type)
            return yaml.safe_dump(parsed_form, sort_keys=False, allow_unicode=True)

        if self._is_text_like_content_type(content_type):
            return self._render_text_or_binary_preview(payload_raw, content_type)

        return self._render_text_or_binary_preview(payload_raw, content_type)

    def _render_text_or_binary_preview(self, payload_raw: bytes, content_type: str | None) -> str:
        try:
            decoded = payload_raw.decode("utf-8")
        except UnicodeDecodeError:
            return self._render_binary_preview(payload_raw, content_type)

        return yaml.safe_dump({"text": decoded}, sort_keys=False, allow_unicode=True)

    def _render_binary_preview(self, payload_raw: bytes, content_type: str | None) -> str:
        return yaml.safe_dump(
            {
                "binary_payload": True,
                "content_type": content_type or "application/octet-stream",
                "payload_size_bytes": len(payload_raw),
            },
            sort_keys=False,
            allow_unicode=True,
        )

    def normalize_source_ip(self, client_host: str | None, forwarded_for: str | None) -> str:
        if client_host and client_host in self.settings.trusted_proxies and forwarded_for:
            first_forwarded = forwarded_for.split(",", maxsplit=1)[0].strip()
            if self._is_valid_ip_address(first_forwarded):
                return first_forwarded
        return client_host or "unknown"

    def sanitized_headers(self, request: Request) -> dict[str, str]:
        sanitized: dict[str, str] = {}
        for header_name in self.settings.header_allowlist:
            value = request.headers.get(header_name)
            if value:
                sanitized[header_name] = value
        return sanitized

    def _is_valid_ip_address(self, value: str) -> bool:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    def _is_json_media_type(self, content_type: str | None) -> bool:
        if content_type is None:
            return False
        return content_type == "application/json" or content_type.endswith("+json")

    def _is_text_like_content_type(self, content_type: str | None) -> bool:
        if content_type is None:
            return False
        return content_type.startswith("text/")


def get_webhook_ingestion_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    rate_limiter: InMemoryRateLimiter = Depends(get_hook_rate_limiter),
) -> WebhookIngestionService:
    return WebhookIngestionService(
        session=session,
        session_factory=sessionmaker(
            bind=session.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        ),
        settings=settings,
        rate_limiter=rate_limiter,
    )