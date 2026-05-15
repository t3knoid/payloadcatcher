from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173"],
        alias="CORS_ALLOW_ORIGINS",
    )
    trusted_proxies: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "::1"],
        alias="TRUSTED_PROXIES",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
