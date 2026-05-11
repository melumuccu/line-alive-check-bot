from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import Settings

BOOTSTRAP_ALERT_AFTER_HOURS = 3
BOOTSTRAP_SCHEDULE_TIMES = ("09:00", "12:00", "18:00")

CHECK_INS_SCHEMA = """
CREATE TABLE IF NOT EXISTS check_ins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    scheduled_at TEXT NOT NULL,
    sent_at TEXT,
    replied_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'success', 'alert')),
    FOREIGN KEY(schedule_id) REFERENCES message_schedules(id)
)
"""

MESSAGE_SCHEDULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS message_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    time_of_day TEXT NOT NULL,
    days_of_week TEXT NOT NULL CHECK(days_of_week = 'daily'),
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    UNIQUE(time_of_day, days_of_week)
)
"""

APP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CHECK_INS_UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_check_ins_schedule_occurrence
ON check_ins(schedule_id, scheduled_at)
"""


def ensure_database_directory(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(settings: Settings) -> sqlite3.Connection:
    ensure_database_directory(settings.database_path)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(settings: Settings) -> None:
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection(settings) as connection:
        connection.execute(MESSAGE_SCHEDULES_SCHEMA)
        connection.execute(APP_SETTINGS_SCHEMA)
        connection.execute(CHECK_INS_SCHEMA)
        connection.execute(CHECK_INS_UNIQUE_INDEX)

        connection.execute(
            """
            INSERT OR IGNORE INTO app_settings(key, value, updated_at)
            VALUES(?, ?, ?)
            """,
            ("alert_after_hours", str(BOOTSTRAP_ALERT_AFTER_HOURS), now),
        )

        for index, time_of_day in enumerate(BOOTSTRAP_SCHEDULE_TIMES, start=1):
            connection.execute(
                """
                INSERT OR IGNORE INTO message_schedules(label, time_of_day, days_of_week, is_active, updated_at)
                VALUES(?, ?, 'daily', 1, ?)
                """,
                (default_schedule_label(index), time_of_day, now),
            )

        connection.commit()


def default_schedule_label(index: int) -> str:
    labels = {1: "朝", 2: "昼", 3: "夜"}
    return labels.get(index, f"定期{index}")


def queue_due_check_ins(settings: Settings, scheduled_at: datetime) -> list[sqlite3.Row]:
    scheduled_time = scheduled_at.strftime("%H:%M")
    scheduled_at_iso = scheduled_at.isoformat(timespec="minutes")

    with get_connection(settings) as connection:
        schedules = connection.execute(
            """
            SELECT id, label, time_of_day
            FROM message_schedules
            WHERE is_active = 1 AND days_of_week = 'daily' AND time_of_day = ?
            ORDER BY id ASC
            """,
            (scheduled_time,),
        ).fetchall()

        for schedule in schedules:
            connection.execute(
                """
                INSERT OR IGNORE INTO check_ins(schedule_id, scheduled_at, status)
                VALUES(?, ?, 'pending')
                """,
                (schedule["id"], scheduled_at_iso),
            )

        connection.commit()
        return schedules


def database_exists(settings: Settings) -> bool:
    return settings.database_path.exists()
