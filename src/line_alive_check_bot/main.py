from __future__ import annotations

from contextlib import asynccontextmanager
import re
import sqlite3

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .config import get_settings

TIME_OF_DAY_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class MessageScheduleResponse(BaseModel):
    id: int
    label: str
    time_of_day: str
    days_of_week: str
    is_active: bool
    updated_at: str


class MessageScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(min_length=1)
    time_of_day: str = Field(min_length=5, max_length=5)
    days_of_week: str = "daily"
    is_active: bool = True


class MessageScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(min_length=1)
    time_of_day: str = Field(min_length=5, max_length=5)
    days_of_week: str = "daily"
    is_active: bool


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


def serialize_message_schedule(schedule: sqlite3.Row) -> MessageScheduleResponse:
    return MessageScheduleResponse(
        id=schedule["id"],
        label=schedule["label"],
        time_of_day=schedule["time_of_day"],
        days_of_week=schedule["days_of_week"],
        is_active=bool(schedule["is_active"]),
        updated_at=schedule["updated_at"],
    )


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="setting key must not be empty",
        )

    return normalized_key


def normalize_setting_value(setting_key: str, setting_value: str) -> str:
    normalized_value = setting_value.strip()
    if not normalized_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="setting value must not be empty",
        )

    if setting_key != "alert_after_hours":
        return normalized_value

    try:
        alert_after_hours = int(normalized_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="alert_after_hours must be an integer",
        ) from exc

    if alert_after_hours < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="alert_after_hours must be at least 1",
        )

    return str(alert_after_hours)


def normalize_schedule_id(schedule_id: int) -> int:
    if schedule_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="schedule id must be positive",
        )

    return schedule_id


def normalize_schedule_label(label: str) -> str:
    normalized_label = label.strip()
    if not normalized_label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="schedule label must not be empty",
        )

    return normalized_label


def normalize_time_of_day(time_of_day: str) -> str:
    normalized_time = time_of_day.strip()
    if not TIME_OF_DAY_PATTERN.fullmatch(normalized_time):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="time_of_day must be in HH:MM format",
        )

    return normalized_time


def normalize_days_of_week(days_of_week: str) -> str:
    normalized_days = days_of_week.strip().lower()
    if normalized_days != "daily":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="days_of_week must be 'daily'",
        )

    return normalized_days


def get_app_setting_or_404(setting_key: str) -> sqlite3.Row:
    current_settings = get_settings()
    setting = db.get_app_setting(current_settings, setting_key)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app setting not found")

    return setting


def get_message_schedule_or_404(schedule_id: int) -> sqlite3.Row:
    current_settings = get_settings()
    schedule = db.get_message_schedule(current_settings, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="message schedule not found",
        )

    return schedule


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


@app.get("/admin/message-schedules", response_model=list[MessageScheduleResponse])
def list_message_schedules() -> list[MessageScheduleResponse]:
    current_settings = get_settings()
    schedules = db.list_message_schedules(current_settings)
    return [serialize_message_schedule(schedule) for schedule in schedules]


@app.get("/admin/message-schedules/{schedule_id}", response_model=MessageScheduleResponse)
def get_message_schedule(schedule_id: int) -> MessageScheduleResponse:
    normalized_schedule_id = normalize_schedule_id(schedule_id)
    return serialize_message_schedule(get_message_schedule_or_404(normalized_schedule_id))


@app.post(
    "/admin/message-schedules",
    response_model=MessageScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message_schedule(payload: MessageScheduleCreateRequest) -> MessageScheduleResponse:
    normalized_label = normalize_schedule_label(payload.label)
    normalized_time = normalize_time_of_day(payload.time_of_day)
    normalized_days = normalize_days_of_week(payload.days_of_week)
    current_settings = get_settings()

    try:
        schedule = db.create_message_schedule(
            current_settings,
            normalized_label,
            normalized_time,
            normalized_days,
            payload.is_active,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="message schedule already exists",
        ) from exc

    return serialize_message_schedule(schedule)


@app.put("/admin/message-schedules/{schedule_id}", response_model=MessageScheduleResponse)
def update_message_schedule(
    schedule_id: int,
    payload: MessageScheduleUpdateRequest,
) -> MessageScheduleResponse:
    normalized_schedule_id = normalize_schedule_id(schedule_id)
    normalized_label = normalize_schedule_label(payload.label)
    normalized_time = normalize_time_of_day(payload.time_of_day)
    normalized_days = normalize_days_of_week(payload.days_of_week)
    current_settings = get_settings()

    try:
        schedule = db.update_message_schedule(
            current_settings,
            normalized_schedule_id,
            normalized_label,
            normalized_time,
            normalized_days,
            payload.is_active,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="message schedule already exists",
        ) from exc

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="message schedule not found",
        )

    return serialize_message_schedule(schedule)


@app.delete("/admin/message-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_schedule(schedule_id: int) -> Response:
    normalized_schedule_id = normalize_schedule_id(schedule_id)
    current_settings = get_settings()
    deleted = db.delete_message_schedule(current_settings, normalized_schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="message schedule not found",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
