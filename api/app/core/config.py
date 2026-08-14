from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GEOP API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    web_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    database_url: str | None = None
    database_url_file: str | None = None
    database_echo: bool = False
    jwt_secret: str = "registro-development-only-change-me"
    jwt_secret_file: str | None = None
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    chess_hotel_integration_key: str = "chess-hotel-development"
    chess_hotel_integration_key_file: str | None = None
    chess_hotel_company_slug: str = "aero-hotel"
    registro_web_url: str = "http://localhost:3000"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "registro"
    s3_access_key_file: str | None = None
    s3_secret_key: str = "registro-dev-secret"
    s3_secret_key_file: str | None = None
    s3_bucket: str = "registro-attachments"
    s3_public_url: str = "http://localhost:9000"
    attachment_max_size_mb: int = 10
    attachment_max_per_entity: int = 20
    redis_url: str = "redis://localhost:6379/0"
    brevo_api_key: str = ""
    mail_from_address: str = "noreply@registro.app"
    mail_from_name: str = "GEOP"
    asaas_api_key: str = ""
    asaas_api_key_file: str | None = None
    asaas_api_url: str = "https://sandbox.asaas.com/api/v3"
    asaas_webhook_token: str = ""
    asaas_webhook_token_file: str | None = None
    sentry_dsn: str = ""

    @field_validator("web_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def blank_database_url_is_unconfigured(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url is None and settings.database_url_file:
        settings.database_url = Path(settings.database_url_file).read_text(encoding="utf-8").strip()
    if settings.jwt_secret_file:
        settings.jwt_secret = Path(settings.jwt_secret_file).read_text(encoding="utf-8").strip()
    if settings.chess_hotel_integration_key_file:
        settings.chess_hotel_integration_key = (
            Path(settings.chess_hotel_integration_key_file).read_text(encoding="utf-8").strip()
        )
    if settings.s3_access_key_file:
        settings.s3_access_key = (
            Path(settings.s3_access_key_file).read_text(encoding="utf-8").strip()
        )
    if settings.s3_secret_key_file:
        settings.s3_secret_key = (
            Path(settings.s3_secret_key_file).read_text(encoding="utf-8").strip()
        )
    if settings.asaas_api_key_file:
        settings.asaas_api_key = (
            Path(settings.asaas_api_key_file).read_text(encoding="utf-8").strip()
        )
    if settings.asaas_webhook_token_file:
        settings.asaas_webhook_token = (
            Path(settings.asaas_webhook_token_file).read_text(encoding="utf-8").strip()
        )
    insecure_default = "registro-development-only-change-me"
    if settings.environment == "production" and (
        settings.jwt_secret == insecure_default or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError("JWT_SECRET de produção deve ter pelo menos 32 caracteres")
    if settings.environment == "production" and (
        settings.chess_hotel_integration_key == "chess-hotel-development"
        or len(settings.chess_hotel_integration_key) < 32
    ):
        raise RuntimeError(
            "CHESS_HOTEL_INTEGRATION_KEY de produção deve ter pelo menos 32 caracteres"
        )
    if settings.environment == "production" and "*" in settings.web_origins:
        raise RuntimeError("WEB_ORIGINS não pode conter '*' em produção")
    return settings
