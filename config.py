from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    secret_key: str = Field(..., alias="SECRET_KEY")
    session_key_1: str = Field(..., alias="SESSION_KEY_1")
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_key: str = Field(..., alias="SUPABASE_KEY")
    supabase_bucket: str = Field(..., alias="SUPABASE_BUCKET")
    frontend_origins: str = Field(..., alias="FRONTEND_ORIGINS")
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    telegram_auth_token: str | None = Field(default=None, alias="TELEGRAM_AUTH_TOKEN")
    telegram_bot_username: str | None = Field(default=None, alias="TELEGRAM_BOT_USERNAME")
    telegram_api_id: int | None = Field(default=None, alias="TELEGRAM_API_ID")
    telegram_api_hash: str | None = Field(default=None, alias="TELEGRAM_API_HASH")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
