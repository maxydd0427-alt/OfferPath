from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OfferPath"
    env: str = "local"
    database_url: str = "sqlite:///./offerpath.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    upload_dir: str = "./storage/resumes"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OFFERPATH_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_backend(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "sqlite"
    if database_url.startswith(("postgresql", "postgres")):
        return "postgresql"
    return "unknown"
