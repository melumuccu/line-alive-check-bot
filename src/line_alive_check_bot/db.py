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


def list_message_schedules(settings: Settings) -> list[sqlite3.Row]:
    with get_connection(settings) as connection:
        return connection.execute(
            """
            SELECT id, label, time_of_day, days_of_week, is_active, updated_at
            FROM message_schedules
            ORDER BY time_of_day ASC, id ASC
            """
        ).fetchall()


def get_message_schedule(settings: Settings, schedule_id: int) -> sqlite3.Row | None:
    with get_connection(settings) as connection:
        return connection.execute(
            """
            SELECT id, label, time_of_day, days_of_week, is_active, updated_at
            FROM message_schedules
            WHERE id = ?
            """,
            (schedule_id,),
        ).fetchone()


def create_message_schedule(
    settings: Settings,
    label: str,
    time_of_day: str,
    days_of_week: str,
    is_active: bool,
) -> sqlite3.Row:
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO message_schedules(label, time_of_day, days_of_week, is_active, updated_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (label, time_of_day, days_of_week, int(is_active), now),
        )
        schedule = connection.execute(
            """
            SELECT id, label, time_of_day, days_of_week, is_active, updated_at
            FROM message_schedules
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        connection.commit()

    if schedule is None:
        raise RuntimeError(f"failed to create message schedule: {label}")

    return schedule


def update_message_schedule(
    settings: Settings,
    schedule_id: int,
    label: str,
    time_of_day: str,
    days_of_week: str,
    is_active: bool,
) -> sqlite3.Row | None:
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection(settings) as connection:
        updated = connection.execute(
            """
            UPDATE message_schedules
            SET label = ?, time_of_day = ?, days_of_week = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (label, time_of_day, days_of_week, int(is_active), now, schedule_id),
        )
        if updated.rowcount == 0:
            connection.commit()
            return None

        schedule = connection.execute(
            """
            SELECT id, label, time_of_day, days_of_week, is_active, updated_at
            FROM message_schedules
            WHERE id = ?
            """,
            (schedule_id,),
        ).fetchone()
        connection.commit()

    return schedule


def delete_message_schedule(settings: Settings, schedule_id: int) -> bool:
    with get_connection(settings) as connection:
        deleted = connection.execute(
            """
            DELETE FROM message_schedules
            WHERE id = ?
            """,
            (schedule_id,),
        )
        connection.commit()

    return deleted.rowcount > 0


def list_app_settings(settings: Settings) -> list[sqlite3.Row]:
    with get_connection(settings) as connection:
        return connection.execute(
            """
            SELECT key, value, updated_at
            FROM app_settings
            ORDER BY key ASC
            """
        ).fetchall()


def get_app_setting(settings: Settings, key: str) -> sqlite3.Row | None:
    with get_connection(settings) as connection:
        return connection.execute(
            """
            SELECT key, value, updated_at
            FROM app_settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()


def create_app_setting(settings: Settings, key: str, value: str) -> sqlite3.Row:
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection(settings) as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value, updated_at)
            VALUES(?, ?, ?)
            """,
            (key, value, now),
        )
        setting = connection.execute(
            """
            SELECT key, value, updated_at
            FROM app_settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
        connection.commit()

    if setting is None:
        raise RuntimeError(f"failed to create app setting: {key}")

    return setting


def update_app_setting(settings: Settings, key: str, value: str) -> sqlite3.Row | None:
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection(settings) as connection:
        updated = connection.execute(
            """
            UPDATE app_settings
            SET value = ?, updated_at = ?
            WHERE key = ?
            """,
            (value, now, key),
        )
        if updated.rowcount == 0:
            connection.commit()
            return None

        setting = connection.execute(
            """
            SELECT key, value, updated_at
            FROM app_settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
        connection.commit()

    return setting


def delete_app_setting(settings: Settings, key: str) -> bool:
    with get_connection(settings) as connection:
        deleted = connection.execute(
            """
            DELETE FROM app_settings
            WHERE key = ?
            """,
            (key,),
        )
        connection.commit()

    return deleted.rowcount > 0


def database_exists(settings: Settings) -> bool:
    return settings.database_path.exists()
