from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "line-alive-check-bot"
    database_path: Path = Path("/data/app.db")
    default_alert_after_hours: int = 3
    default_schedule_times: str = "09:00,12:00,18:00"
    scheduler_poll_seconds: int = 60
    timezone: str = "Asia/Tokyo"

    @property
    def schedule_times(self) -> list[str]:
        return [value.strip() for value in self.default_schedule_times.split(",") if value.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
