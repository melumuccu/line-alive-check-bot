from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import database_exists, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(get_settings())
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/healthz")
def healthcheck() -> dict[str, object]:
    current_settings = get_settings()
    return {
        "status": "ok",
        "service": "api",
        "database_exists": database_exists(current_settings),
        "database_path": str(current_settings.database_path),
        "timezone": current_settings.timezone,
    }
