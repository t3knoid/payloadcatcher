from app.core.config import Settings


def test_settings_parse_comma_delimited_list_env_values(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173, https://payloadcat.ch")
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1,::1")

    settings = Settings(_env_file=None)

    assert settings.cors_allow_origins == [
        "http://127.0.0.1:5173",
        "https://payloadcat.ch",
    ]
    assert settings.trusted_proxies == ["127.0.0.1", "::1"]
