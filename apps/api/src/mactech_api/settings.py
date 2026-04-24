from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_async_pg_url(value: str) -> str:
    """Railway / Heroku / many hosting providers inject `postgresql://...` or
    `postgres://...`. Our async SQLAlchemy engine needs `postgresql+asyncpg://...`.
    """
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        value = "postgresql+asyncpg://" + value[len("postgresql://") :]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    database_url: str
    redis_url: str = Field(default="redis://localhost:6379/0")

    s3_endpoint: str = Field(default="http://localhost:9000")
    s3_region: str = Field(default="us-east-1")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="mactech-documents")

    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_from: str = Field(default="noreply@mactechsolutionsllc.com")

    mactech_tenant_slug: str = Field(default="mactech")

    sam_api_key: str = Field(default="")
    apify_token: str = Field(default="")
    serpapi_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    voyage_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")

    clerk_publishable_key: str = Field(default="")
    clerk_secret_key: str = Field(default="")
    clerk_jwt_key: str = Field(default="")

    sentry_dsn: str = Field(default="")
    posthog_api_key: str = Field(default="")

    @field_validator("database_url")
    @classmethod
    def _ensure_asyncpg(cls, v: str) -> str:
        return _normalize_async_pg_url(v)


settings = Settings()  # type: ignore[call-arg]
