from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException

from line_alive_check_bot import db
from line_alive_check_bot.config import Settings
from line_alive_check_bot.main import (
    list_check_ins,
    create_message_schedule,
    delete_message_schedule,
    get_message_schedule,
    list_message_schedules,
    update_message_schedule,
    MessageScheduleCreateRequest,
    MessageScheduleUpdateRequest,
)


class MessageSchedulesApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(database_path=Path(self.temporary_directory.name) / "app.db")
        db.init_db(self.settings)

    def test_message_schedule_crud_flow(self) -> None:
        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            schedules = list_message_schedules()

            self.assertEqual(len(schedules), 3)

            created_schedule = create_message_schedule(
                MessageScheduleCreateRequest(
                    label="就寝前",
                    time_of_day="22:30",
                    is_active=False,
                )
            )

            self.assertEqual(created_schedule.label, "就寝前")
            self.assertEqual(created_schedule.time_of_day, "22:30")
            self.assertEqual(created_schedule.days_of_week, "daily")
            self.assertFalse(created_schedule.is_active)

            schedule_id = created_schedule.id
            fetched_schedule = get_message_schedule(schedule_id)

            self.assertEqual(fetched_schedule.id, schedule_id)

            updated_schedule = update_message_schedule(
                schedule_id,
                MessageScheduleUpdateRequest(
                    label="深夜",
                    time_of_day="22:45",
                    days_of_week="daily",
                    is_active=True,
                ),
            )

            self.assertEqual(updated_schedule.label, "深夜")
            self.assertEqual(updated_schedule.time_of_day, "22:45")
            self.assertTrue(updated_schedule.is_active)

            delete_response = delete_message_schedule(schedule_id)

            self.assertEqual(delete_response.status_code, 204)

            with self.assertRaises(HTTPException) as context:
                get_message_schedule(schedule_id)

            self.assertEqual(context.exception.status_code, 404)


class CheckInsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(database_path=Path(self.temporary_directory.name) / "app.db")
        db.init_db(self.settings)

    def test_list_check_ins_returns_latest_history_first(self) -> None:
        with db.get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO check_ins(schedule_id, scheduled_at, sent_at, replied_at, status)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "2026-05-11T09:00",
                    "2026-05-11T09:00:10",
                    None,
                    "pending",
                ),
            )
            connection.execute(
                """
                INSERT INTO check_ins(schedule_id, scheduled_at, sent_at, replied_at, status)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    2,
                    "2026-05-11T12:00",
                    "2026-05-11T12:00:05",
                    "2026-05-11T12:03:00",
                    "success",
                ),
            )
            connection.commit()

        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            history = list_check_ins()

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].schedule_id, 2)
        self.assertEqual(history[0].schedule_label, "昼")
        self.assertEqual(history[0].schedule_time_of_day, "12:00")
        self.assertEqual(history[0].status, "success")
        self.assertEqual(history[1].schedule_id, 1)
        self.assertEqual(history[1].schedule_label, "朝")
        self.assertEqual(history[1].status, "pending")


class MessageSchedulesValidationApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(database_path=Path(self.temporary_directory.name) / "app.db")
        db.init_db(self.settings)

    def test_create_message_schedule_rejects_invalid_time_of_day(self) -> None:
        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            with self.assertRaises(HTTPException) as context:
                create_message_schedule(
                    MessageScheduleCreateRequest(
                        label="不正な時刻",
                        time_of_day="24:00",
                        is_active=True,
                    )
                )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail, "time_of_day must be in HH:MM format")
