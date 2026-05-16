from app.core.config import Settings


def test_settings_parse_comma_delimited_list_env_values(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173, https://payloadcat.ch")
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")
    monkeypatch.setenv("HEADER_ALLOWLIST", "user-agent, referer, accept-language")

    settings = Settings(_env_file=None)

    assert settings.cors_allow_origins == [
        "http://127.0.0.1:5173",
        "https://payloadcat.ch",
    ]
    assert settings.trusted_proxies == ["127.0.0.1", "::1"]
    assert settings.header_allowlist == ["user-agent", "referer", "accept-language"]


def test_settings_include_hook_payload_limit_and_content_type_header_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.hook_payload_max_bytes == 1048576
    assert settings.rate_limit_per_minute == 60
    assert settings.header_allowlist == [
        "content-type",
        "user-agent",
        "referer",
        "accept-language",
    ]
