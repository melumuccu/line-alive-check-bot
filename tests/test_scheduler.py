from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from line_alive_check_bot import db, scheduler
from line_alive_check_bot.config import Settings


class FrozenDateTime(datetime):
    current: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.current.replace(tzinfo=None)

        return cls.current.astimezone(tz)


class SchedulerMessageDispatchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(
            database_path=Path(self.temporary_directory.name) / "app.db",
            line_channel_access_token="test-access-token",
            line_user_id="U1234567890",
        )
        db.init_db(self.settings)

    def test_run_once_sends_new_check_in_and_marks_sent_at(self) -> None:
        FrozenDateTime.current = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        with (
            patch("line_alive_check_bot.scheduler.get_settings", return_value=self.settings),
            patch("line_alive_check_bot.scheduler.datetime", FrozenDateTime),
            patch("line_alive_check_bot.scheduler.send_check_in_message", create=True) as send_check_in_message,
        ):
            first_run = scheduler.run_once()
            second_run = scheduler.run_once()

        self.assertEqual(first_run, 1)
        self.assertEqual(second_run, 0)
        self.assertEqual(send_check_in_message.call_count, 1)

        sent_check_in = send_check_in_message.call_args.args[1]
        self.assertEqual(sent_check_in["schedule_id"], 1)
        self.assertEqual(sent_check_in["schedule_label"], "朝")
        self.assertEqual(sent_check_in["status"], "pending")

        with db.get_connection(self.settings) as connection:
            stored_check_in = connection.execute(
                """
                SELECT sent_at, status
                FROM check_ins
                WHERE schedule_id = ?
                """,
                (1,),
            ).fetchone()

        self.assertIsNotNone(stored_check_in)
        self.assertIsNotNone(stored_check_in["sent_at"])
        self.assertEqual(stored_check_in["status"], "pending")

    def test_run_once_marks_overdue_pending_check_in_as_alert_and_notifies_slack(self) -> None:
        with db.get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO check_ins(schedule_id, scheduled_at, sent_at, replied_at, status)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "2026-05-11T09:00",
                    "2026-05-11T09:00:00",
                    None,
                    "pending",
                ),
            )
            connection.commit()

        FrozenDateTime.current = datetime(2026, 5, 11, 12, 1, tzinfo=ZoneInfo("Asia/Tokyo"))

        with (
            patch("line_alive_check_bot.scheduler.get_settings", return_value=self.settings),
            patch("line_alive_check_bot.scheduler.datetime", FrozenDateTime),
            patch("line_alive_check_bot.scheduler.send_check_in_message", create=True),
            patch("line_alive_check_bot.scheduler.send_alert_notification", create=True) as send_alert_notification,
        ):
            first_run = scheduler.run_once()
            second_run = scheduler.run_once()

        self.assertEqual(first_run, 0)
        self.assertEqual(second_run, 0)
        self.assertEqual(send_alert_notification.call_count, 1)

        alerted_check_in = send_alert_notification.call_args.args[1]
        self.assertEqual(alerted_check_in["schedule_id"], 1)
        self.assertEqual(alerted_check_in["status"], "alert")

        with db.get_connection(self.settings) as connection:
            stored_check_in = connection.execute(
                """
                SELECT status
                FROM check_ins
                WHERE schedule_id = ?
                """,
                (1,),
            ).fetchone()

        self.assertIsNotNone(stored_check_in)
        self.assertEqual(stored_check_in["status"], "alert")
