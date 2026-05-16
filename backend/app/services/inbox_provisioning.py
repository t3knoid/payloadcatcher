from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
import uuid

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.inbox import ProvisionInboxQuery
from app.core.config import Settings, get_settings
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
    def __init__(self, session: Session, settings: Settings, clock=None) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock or utc_now

    def provision_inbox(self, request: Request, query: ProvisionInboxQuery) -> ProvisionInboxResult:
        now = self.clock()
        active_inbox = self._find_active_inbox(request.cookies.get(self.settings.session_cookie_name), now)
        new_session = active_inbox is None

        if active_inbox is None:
            active_inbox = self._create_inbox(request, now)

        self._record_visit_metadata(active_inbox, request, query, now)
        self.session.commit()

        return ProvisionInboxResult(
            clsid=active_inbox.clsid,
            callback_url=self._build_hook_url(active_inbox.clsid),
            viewer_url=self._build_viewer_url(active_inbox.clsid),
            expires_at=active_inbox.expires_at,
            new_session=new_session,
        )

    def bind_session_cookie(self, response: Response, clsid: str) -> None:
        response.set_cookie(
            key=self.settings.session_cookie_name,
            value=clsid,
            max_age=self.settings.cookie_max_age,
            httponly=True,
            secure=self.settings.cookie_secure,
            samesite=self.settings.cookie_samesite,
            path="/",
        )

    def normalize_source_ip(self, client_host: str | None, forwarded_for: str | None) -> str:
        if client_host and client_host in self.settings.trusted_proxies and forwarded_for:
            first_forwarded = forwarded_for.split(",", maxsplit=1)[0].strip()
            if first_forwarded:
                return first_forwarded
        return client_host or "unknown"

    def _find_active_inbox(self, clsid: str | None, now: datetime) -> Inbox | None:
        if not clsid:
            return None

        statement = select(Inbox).where(Inbox.clsid == clsid, Inbox.expires_at > now)
        return self.session.scalar(statement)

    def _create_inbox(self, request: Request, now: datetime) -> Inbox:
        ttl = timedelta(hours=self.settings.callback_ttl_hours)
        inbox = Inbox(
            clsid=str(uuid.uuid4()),
            source_ip=self.normalize_source_ip(
                request.client.host if request.client else None,
                request.headers.get("x-forwarded-for"),
            ),
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
    ) -> None:
        user_agent = request.headers.get("user-agent")
        visit = VisitMetadata(
            inbox_id=inbox.id,
            visited_at=now,
            source_ip=self.normalize_source_ip(
                request.client.host if request.client else None,
                request.headers.get("x-forwarded-for"),
            ),
            referer_url=request.headers.get("referer"),
            user_agent=user_agent,
            browser=self._detect_browser(user_agent),
            device=self._detect_device(user_agent),
            lang=self._primary_language(request.headers.get("accept-language")),
            tz=query.timezone,
            locality=None,
            headers_json=self._sanitized_headers(request),
            consent=False,
        )
        self.session.add(visit)

    def _sanitized_headers(self, request: Request) -> dict[str, str]:
        sanitized: dict[str, str] = {}
        for header_name in self.settings.header_allowlist:
            value = request.headers.get(header_name)
            if value:
                sanitized[header_name] = value
        return sanitized

    def _build_hook_url(self, clsid: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/hook/{clsid}"

    def _build_viewer_url(self, clsid: str) -> str:
        return f"{self.settings.base_url.rstrip('/')}/inbox/{clsid}"

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
) -> InboxProvisioningService:
    return InboxProvisioningService(session=session, settings=settings)