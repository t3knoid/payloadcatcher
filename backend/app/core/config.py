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
    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173"],
        alias="CORS_ALLOW_ORIGINS",
    )
    trusted_proxies: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1", "::1"],
        alias="TRUSTED_PROXIES",
    )

    @field_validator("cors_allow_origins", "trusted_proxies", mode="before")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
