from __future__ import annotations

from contextlib import asynccontextmanager
import sqlite3

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .config import get_settings


class AppSettingResponse(BaseModel):
    key: str
    value: str
    updated_at: str


class AppSettingCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class AppSettingUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    value: str = Field(min_length=1)


def serialize_app_setting(setting: sqlite3.Row) -> AppSettingResponse:
    return AppSettingResponse(
        key=setting["key"],
        value=setting["value"],
        updated_at=setting["updated_at"],
    )


def normalize_setting_key(setting_key: str) -> str:
    normalized_key = setting_key.strip()
    if not normalized_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="setting key must not be empty",
        )

    return normalized_key


def normalize_setting_value(setting_key: str, setting_value: str) -> str:
    normalized_value = setting_value.strip()
    if not normalized_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="setting value must not be empty",
        )

    if setting_key != "alert_after_hours":
        return normalized_value

    try:
        alert_after_hours = int(normalized_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="alert_after_hours must be an integer",
        ) from exc

    if alert_after_hours < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="alert_after_hours must be at least 1",
        )

    return str(alert_after_hours)


def get_app_setting_or_404(setting_key: str) -> sqlite3.Row:
    current_settings = get_settings()
    setting = db.get_app_setting(current_settings, setting_key)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app setting not found")

    return setting


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db(get_settings())
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/healthz")
def healthcheck() -> dict[str, object]:
    current_settings = get_settings()
    return {
        "status": "ok",
        "service": "api",
        "database_exists": db.database_exists(current_settings),
        "database_path": str(current_settings.database_path),
        "timezone": current_settings.timezone,
    }


@app.get("/admin/app-settings", response_model=list[AppSettingResponse])
def list_app_settings() -> list[AppSettingResponse]:
    current_settings = get_settings()
    settings_rows = db.list_app_settings(current_settings)
    return [serialize_app_setting(setting) for setting in settings_rows]


@app.get("/admin/app-settings/{setting_key}", response_model=AppSettingResponse)
def get_app_setting(setting_key: str) -> AppSettingResponse:
    normalized_key = normalize_setting_key(setting_key)
    return serialize_app_setting(get_app_setting_or_404(normalized_key))


@app.post(
    "/admin/app-settings",
    response_model=AppSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_app_setting(payload: AppSettingCreateRequest) -> AppSettingResponse:
    normalized_key = normalize_setting_key(payload.key)
    normalized_value = normalize_setting_value(normalized_key, payload.value)
    current_settings = get_settings()

    try:
        setting = db.create_app_setting(current_settings, normalized_key, normalized_value)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="app setting already exists",
        ) from exc

    return serialize_app_setting(setting)


@app.put("/admin/app-settings/{setting_key}", response_model=AppSettingResponse)
def update_app_setting(setting_key: str, payload: AppSettingUpdateRequest) -> AppSettingResponse:
    normalized_key = normalize_setting_key(setting_key)
    normalized_value = normalize_setting_value(normalized_key, payload.value)
    current_settings = get_settings()
    setting = db.update_app_setting(current_settings, normalized_key, normalized_value)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app setting not found")

    return serialize_app_setting(setting)


@app.delete("/admin/app-settings/{setting_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app_setting(setting_key: str) -> Response:
    normalized_key = normalize_setting_key(setting_key)
    current_settings = get_settings()
    deleted = db.delete_app_setting(current_settings, normalized_key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app setting not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
