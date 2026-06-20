from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "Wealth Manager"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+psycopg://cm@127.0.0.1:5432/cm"

    SECRET_KEY: str = "change-me-in-production-please"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Daily portfolio-snapshot scheduler. Disabled by default (and in tests);
    # snapshot logic is exercised directly and via /snapshots/rebuild.
    ENABLE_SCHEDULER: bool = False
    SNAPSHOT_HOUR_UTC: int = 0
    SNAPSHOT_MINUTE_UTC: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
