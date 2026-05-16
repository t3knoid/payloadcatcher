from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import ipaddress
import logging
import re
from typing import Literal, cast
import uuid

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas.inbox import ProvisionInboxQuery, VisitMetadataUpdateRequest
from app.core.config import Settings, get_settings
from app.infrastructure.rate_limit import InMemoryRateLimiter, get_request_rate_limiter
from app.persistence.models import Inbox, VisitMetadata
from app.persistence.session import get_db_session


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ProvisionInboxResult:
    clsid: str
    callback_url: str
    viewer_url: str
    expires_at: datetime
    new_session: bool


class InboxProvisioningService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        rate_limiter: InMemoryRateLimiter | None = None,
        clock=None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.rate_limiter = rate_limiter
        self.clock = clock or utc_now
        self.logger = logging.getLogger("payloadcatcher.inbox")

    def provision_inbox(self, request: Request, query: ProvisionInboxQuery) -> ProvisionInboxResult:
        now = self.clock()
        current_source_ip = self.normalize_source_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
        )
        self.enforce_rate_limit(current_source_ip, scope="bootstrap")
        active_inbox = self._find_active_inbox(
            request.cookies.get(self.settings.session_cookie_name),
            now,
            current_source_ip,
        )
        new_session = active_inbox is None

        if active_inbox is None:
            active_inbox = self._create_inbox(current_source_ip, now)

        self._record_visit_metadata(active_inbox, request, query, now, current_source_ip)
        self.session.commit()

        return ProvisionInboxResult(
            clsid=active_inbox.clsid,
            callback_url=self._build_hook_url(active_inbox.clsid),
            viewer_url=self._build_viewer_url(active_inbox.clsid),
            expires_at=self._response_datetime(active_inbox.expires_at),
            new_session=new_session,
        )

    def bind_session_cookie(self, response: Response, clsid: str) -> None:
        response.set_cookie(
            key=self.settings.session_cookie_name,
            value=clsid,
            max_age=self.settings.cookie_max_age,
            httponly=True,
            secure=self.settings.cookie_secure,
            samesite=cast(Literal["lax", "strict", "none"], self.settings.cookie_samesite),
            path="/",
        )

    def normalize_source_ip(self, client_host: str | None, forwarded_for: str | None) -> str:
        if client_host and client_host in self.settings.trusted_proxies and forwarded_for:
            first_forwarded = forwarded_for.split(",", maxsplit=1)[0].strip()
            if self._is_valid_ip_address(first_forwarded):
                return first_forwarded
        return client_host or "unknown"

    def _is_valid_ip_address(self, value: str) -> bool:
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    def reuse_allowed_for_source_ip(self, stored_source_ip: str, current_source_ip: str, clsid: str) -> bool:
        if stored_source_ip != current_source_ip:
            self.logger.info(
                "Source IP changed for active inbox %s: stored=%s current=%s",
                clsid,
                stored_source_ip,
                current_source_ip,
            )
        return True

    def enforce_rate_limit(self, source_ip: str, scope: str) -> None:
        if self.rate_limiter is None:
            return

        retry_after = self.rate_limiter.check_and_consume(f"{scope}:{source_ip}")
        if retry_after is None:
            return

        self.logger.warning(
            "%s rate limit exceeded for source_ip=%s retry_after=%s",
            scope.capitalize(),
            source_ip,
            retry_after,
        )
        raise ApiError(
            429,
            "rate_limited",
            "Too many requests",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    def _find_active_inbox(self, clsid: str | None, now: datetime, current_source_ip: str) -> Inbox | None:
        if not clsid:
            return None

        statement = select(Inbox).where(Inbox.clsid == clsid, Inbox.expires_at > now)
        inbox = self.session.scalar(statement)
        if inbox is None:
            return None
        if not self.reuse_allowed_for_source_ip(inbox.source_ip, current_source_ip, inbox.clsid):
            return None
        return inbox

    def _create_inbox(self, source_ip: str, now: datetime) -> Inbox:
        ttl = timedelta(hours=self.settings.callback_ttl_hours)
        inbox = Inbox(
            clsid=str(uuid.uuid4()),
            source_ip=source_ip,
            issued_at=now,
            expires_at=now + ttl,
        )
        self.session.add(inbox)
        self.session.flush()
        return inbox

    def _record_visit_metadata(
        self,
        inbox: Inbox,
        request: Request,
        query: ProvisionInboxQuery,
        now: datetime,
        source_ip: str,
    ) -> None:
        user_agent = request.headers.get("user-agent")
        visit = VisitMetadata(
            inbox_id=inbox.id,
            visited_at=now,
            source_ip=source_ip,
            referer_url=request.headers.get("referer"),
            user_agent=user_agent,
            browser=self._detect_browser(user_agent),
            device=self._detect_device(user_agent),
            lang=self._primary_language(request.headers.get("accept-language")),
            tz=query.timezone,
            locality=self._resolve_locality(request),
            headers_json=self._sanitized_headers(request),
            consent=False,
        )
        self.session.add(visit)

    def update_visit_metadata(self, request: Request, payload: VisitMetadataUpdateRequest) -> None:
        source_ip = self.normalize_source_ip(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
        )
        self.enforce_rate_limit(source_ip, scope="visit-metadata")
        active_inbox = self._find_active_inbox(
            request.cookies.get(self.settings.session_cookie_name),
            self.clock(),
            source_ip,
        )
        if active_inbox is None:
            raise ApiError(404, "inbox_not_found", "Active inbox not found for session")

        visit = self.session.scalar(
            select(VisitMetadata)
            .where(VisitMetadata.inbox_id == active_inbox.id)
            .order_by(VisitMetadata.visited_at.desc(), VisitMetadata.id.desc())
            .limit(1)
        )
        if visit is None:
            raise ApiError(404, "visit_metadata_not_found", "Visit metadata not found for active inbox")

        gps_lat, gps_lng, gps_consent = self._resolve_gps_capture(payload)
        visit.gps_lat = gps_lat
        visit.gps_lng = gps_lng
        visit.consent = gps_consent
        self.session.commit()

    def _sanitized_headers(self, request: Request) -> dict[str, str]:
        sanitized: dict[str, str] = {}
        for header_name in self.settings.header_allowlist:
            value = request.headers.get(header_name)
            if value:
                sanitized[header_name] = value
        return sanitized

    def _resolve_locality(self, request: Request) -> str | None:
        header_name = self.settings.locality_header_name
        if not header_name:
            return None
        client_host = request.client.host if request.client else None
        if client_host not in self.settings.trusted_proxies:
            return None
        locality = request.headers.get(header_name)
        if not locality:
            return None
        normalized = " ".join(locality.strip().split())
        if not normalized:
            return None
        return normalized[:128]

    def _resolve_gps_capture(self, payload: VisitMetadataUpdateRequest) -> tuple[float | None, float | None, bool]:
        if not payload.gps_consent:
            return None, None, False
        if not self.settings.gps_collection_enabled:
            return None, None, False
        return payload.gps_lat, payload.gps_lng, True

    def _build_hook_url(self, clsid: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/hook/{clsid}"

    def _build_viewer_url(self, clsid: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/inbox/{clsid}"

    def _response_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _primary_language(self, accept_language: str | None) -> str | None:
        if not accept_language:
            return None
        return accept_language.split(",", maxsplit=1)[0].strip() or None

    def _detect_browser(self, user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        patterns = {
            "Edge": r"Edg/",
            "Chrome": r"Chrome/",
            "Firefox": r"Firefox/",
            "Safari": r"Safari/",
        }
        for browser, pattern in patterns.items():
            if re.search(pattern, user_agent):
                return browser
        return "Unknown"

    def _detect_device(self, user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        if re.search(r"iPad|Tablet", user_agent, re.IGNORECASE):
            return "tablet"
        if re.search(r"Mobile|Android|iPhone", user_agent, re.IGNORECASE):
            return "mobile"
        return "desktop"


def get_inbox_provisioning_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    rate_limiter: InMemoryRateLimiter = Depends(get_request_rate_limiter),
) -> InboxProvisioningService:
    return InboxProvisioningService(
        session=session,
        settings=settings,
        rate_limiter=rate_limiter,
    )