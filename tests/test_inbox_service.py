from fastapi import Response
import logging
import pytest
from starlette.requests import Request

from app.api.errors import ApiError
from app.core.config import Settings
from app.infrastructure.rate_limit import InMemoryRateLimiter
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


def test_normalize_source_ip_honors_forwarded_for_from_trusted_proxy_cidr() -> None:
    settings = Settings(_env_file=None, trusted_proxies=["127.0.0.0/24", "::1"])
    service = InboxProvisioningService(session=None, settings=settings)

    trusted_ip = service.normalize_source_ip("127.0.0.42", "203.0.113.10, 10.0.0.1")
    untrusted_ip = service.normalize_source_ip("198.51.100.8", "203.0.113.10, 10.0.0.1")

    assert trusted_ip == "203.0.113.10"
    assert untrusted_ip == "198.51.100.8"


def test_normalize_source_ip_falls_back_when_forwarded_for_is_invalid() -> None:
    settings = Settings(_env_file=None, trusted_proxies=["127.0.0.1", "::1"])
    service = InboxProvisioningService(session=None, settings=settings)

    normalized_ip = service.normalize_source_ip("127.0.0.1", "not-an-ip, 203.0.113.10")

    assert normalized_ip == "127.0.0.1"


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


def test_enforce_rate_limit_logs_violation(caplog) -> None:
    settings = Settings(_env_file=None)
    service = InboxProvisioningService(
        session=None,
        settings=settings,
        rate_limiter=InMemoryRateLimiter(1),
    )

    service.enforce_rate_limit("203.0.113.10", scope="bootstrap")

    with caplog.at_level(logging.WARNING, logger="payloadcatcher.inbox"):
        with pytest.raises(ApiError) as excinfo:
            service.enforce_rate_limit("203.0.113.10", scope="bootstrap")

    assert excinfo.value.status_code == 429
    assert excinfo.value.error_code == "rate_limited"
    assert "Bootstrap rate limit exceeded" in caplog.text


def test_sanitized_headers_keep_only_allowlisted_values() -> None:
    settings = Settings(_env_file=None, header_allowlist=["user-agent", "accept-language"])
    service = InboxProvisioningService(session=None, settings=settings)
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"user-agent", b"Mozilla/5.0"),
                (b"accept-language", b"en-US,en;q=0.9"),
                (b"authorization", b"Bearer secret"),
                (b"cookie", b"session=secret"),
            ],
        }
    )

    sanitized = service._sanitized_headers(request)

    assert sanitized == {
        "user-agent": "Mozilla/5.0",
        "accept-language": "en-US,en;q=0.9",
    }


def test_resolve_locality_uses_trusted_proxy_header_only() -> None:
    settings = Settings(_env_file=None, trusted_proxies=["127.0.0.1"], locality_header_name="x-geo-city")
    service = InboxProvisioningService(session=None, settings=settings)
    trusted_request = Request(
        {
            "type": "http",
            "headers": [(b"x-geo-city", b"Raleigh, NC")],
            "client": ("127.0.0.1", 4321),
        }
    )
    untrusted_request = Request(
        {
            "type": "http",
            "headers": [(b"x-geo-city", b"Raleigh, NC")],
            "client": ("198.51.100.8", 4321),
        }
    )

    assert service._resolve_locality(trusted_request) == "Raleigh, NC"
    assert service._resolve_locality(untrusted_request) is None


def test_resolve_locality_uses_trusted_proxy_cidr() -> None:
    settings = Settings(_env_file=None, trusted_proxies=["127.0.0.0/24"], locality_header_name="x-geo-city")
    service = InboxProvisioningService(session=None, settings=settings)
    trusted_request = Request(
        {
            "type": "http",
            "headers": [(b"x-geo-city", b"Raleigh, NC")],
            "client": ("127.0.0.42", 4321),
        }
    )

    assert service._resolve_locality(trusted_request) == "Raleigh, NC"