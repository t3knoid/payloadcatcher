from functools import lru_cache
import json
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="PayloadCatcher API")
    environment: str = Field(default="development", alias="ENV")
    base_url: str = Field(default="https://payloadcat.ch", alias="BASE_URL")
    port: int = Field(default=8080, alias="PORT")
    api_bind_host: str = Field(default="127.0.0.1", alias="API_BIND_HOST")
    api_bind_port: int = Field(default=8000, alias="API_BIND_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/payloadcatcher",
        alias="DATABASE_URL",
    )
    callback_ttl_hours: int = Field(default=24, alias="CALLBACK_TTL_HOURS")
    hook_payload_max_bytes: int = Field(default=1048576, alias="HOOK_PAYLOAD_MAX_BYTES")
    header_allowlist: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["content-type", "user-agent", "referer", "accept-language"],
        alias="HEADER_ALLOWLIST",
    )
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173"],
        alias="CORS_ALLOW_ORIGINS",
    )
    trusted_proxies: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1", "::1"],
        alias="TRUSTED_PROXIES",
    )
    session_cookie_name: str = Field(default="payloadcatcher_session", alias="SESSION_COOKIE_NAME")
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")
    cookie_max_age: int = Field(default=86400, alias="COOKIE_MAX_AGE")

    @field_validator("header_allowlist", "cors_allow_origins", "trusted_proxies", mode="before")
    @classmethod
    def parse_list_env(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def normalize_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
