from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from line_alive_check_bot import db
from line_alive_check_bot.config import Settings


class QueueDueCheckInsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(database_path=Path(self.temporary_directory.name) / "app.db")
        db.init_db(self.settings)

    def test_queue_due_check_ins_returns_only_new_rows(self) -> None:
        scheduled_at = datetime.fromisoformat("2026-05-11T08:00:00")

        first_batch = db.queue_due_check_ins(self.settings, scheduled_at)
        second_batch = db.queue_due_check_ins(self.settings, scheduled_at)

        self.assertEqual(len(first_batch), 1)
        self.assertEqual(first_batch[0]["schedule_time_of_day"], "08:00")
        self.assertEqual(first_batch[0]["schedule_label"], "朝")
        self.assertEqual(second_batch, [])

        with db.get_connection(self.settings) as connection:
            queued_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM check_ins
                WHERE schedule_id = ? AND scheduled_at = ?
                """,
                (first_batch[0]["id"], scheduled_at.isoformat(timespec="minutes")),
            ).fetchone()["count"]

        self.assertEqual(queued_count, 1)

    def test_init_db_bootstraps_production_schedule_times_and_alert_threshold(self) -> None:
        schedules = db.list_message_schedules(self.settings)
        alert_after_hours = db.get_app_setting(self.settings, "alert_after_hours")

        self.assertEqual([schedule["time_of_day"] for schedule in schedules], ["08:00", "14:00", "20:00"])
        self.assertIsNotNone(alert_after_hours)
        self.assertEqual(alert_after_hours["value"], "2")

    def test_init_db_does_not_insert_new_default_schedules_into_existing_database(self) -> None:
        with db.get_connection(self.settings) as connection:
            connection.execute("DELETE FROM message_schedules")
            connection.executemany(
                """
                INSERT INTO message_schedules(label, time_of_day, days_of_week, is_active, updated_at)
                VALUES(?, ?, 'daily', 1, ?)
                """,
                [
                    ("朝", "09:00", "2026-05-11T00:00:00"),
                    ("昼", "12:00", "2026-05-11T00:00:00"),
                    ("夜", "18:00", "2026-05-11T00:00:00"),
                ],
            )
            connection.commit()

        db.init_db(self.settings)
        schedules = db.list_message_schedules(self.settings)

        self.assertEqual(len(schedules), 3)
        self.assertEqual([schedule["time_of_day"] for schedule in schedules], ["09:00", "12:00", "18:00"])
