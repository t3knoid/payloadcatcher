from fastapi import Response
import logging

from app.core.config import Settings
from app.services.inbox_provisioning import InboxProvisioningService


def test_bind_session_cookie_uses_secure_defaults() -> None:
    settings = Settings(
        _env_file=None,
        session_cookie_name="payloadcatcher_session",
        cookie_samesite="lax",
        cookie_max_age=86400,
    )
    service = InboxProvisioningService(session=None, settings=settings)
    response = Response()

    service.bind_session_cookie(response, "abc123")

    cookie_header = response.headers["set-cookie"]
    assert "payloadcatcher_session=abc123" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    assert "Secure" in cookie_header
    assert "Max-Age=86400" in cookie_header


def test_normalize_source_ip_honors_forwarded_for_only_from_trusted_proxy() -> None:
    settings = Settings(_env_file=None, trusted_proxies=["127.0.0.1", "::1"])
    service = InboxProvisioningService(session=None, settings=settings)

    trusted_ip = service.normalize_source_ip("127.0.0.1", "203.0.113.10, 10.0.0.1")
    untrusted_ip = service.normalize_source_ip("198.51.100.8", "203.0.113.10, 10.0.0.1")

    assert trusted_ip == "203.0.113.10"
    assert untrusted_ip == "198.51.100.8"


def test_reuse_policy_logs_source_ip_change_as_risk_signal(caplog) -> None:
    settings = Settings(_env_file=None)
    service = InboxProvisioningService(session=None, settings=settings)

    with caplog.at_level(logging.INFO, logger="payloadcatcher.inbox"):
        should_reuse = service.reuse_allowed_for_source_ip(
            stored_source_ip="203.0.113.10",
            current_source_ip="198.51.100.8",
            clsid="550e8400-e29b-41d4-a716-446655440000",
        )

    assert should_reuse is True
    assert "Source IP changed for active inbox" in caplog.text