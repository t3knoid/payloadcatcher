import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parse_comma_delimited_list_env_values(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:5173, http://localhost:5173, https://payloadcat.ch",
    )
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_NETWORK", "192.168.0.0/24, 192.168.10.69/32")
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")
    monkeypatch.setenv("HEADER_ALLOWLIST", "user-agent, referer, accept-language")

    settings = Settings(_env_file=None)

    assert settings.cors_allow_origins == [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://payloadcat.ch",
    ]
    assert settings.cors_allow_origin_networks == ["192.168.0.0/24", "192.168.10.69/32"]
    assert settings.trusted_proxies == ["127.0.0.1", "::1"]
    assert settings.header_allowlist == ["user-agent", "referer", "accept-language"]


def test_settings_include_hook_payload_limit_and_content_type_header_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.hook_payload_max_bytes == 1048576
    assert settings.viewer_payload_preview_chars == 4096
    assert settings.rate_limit_per_minute == 60
    assert settings.header_allowlist == [
        "content-type",
        "user-agent",
        "referer",
        "accept-language",
    ]
    assert settings.cors_allow_origin_networks == []


def test_settings_reject_invalid_cors_allow_origin_network() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_allow_origin_networks=["not-a-network"])


@pytest.mark.parametrize("value", [-1, 0, 1, 2, 3])
def test_settings_reject_non_positive_viewer_payload_preview_chars(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, viewer_payload_preview_chars=value)
