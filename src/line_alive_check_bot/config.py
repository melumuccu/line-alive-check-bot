from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "line-alive-check-bot"
    database_path: Path = Path("/data/app.db")
    scheduler_poll_seconds: int = 60
    timezone: str = "Asia/Tokyo"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
