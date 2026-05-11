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
        scheduled_at = datetime.fromisoformat("2026-05-11T09:00:00")

        first_batch = db.queue_due_check_ins(self.settings, scheduled_at)
        second_batch = db.queue_due_check_ins(self.settings, scheduled_at)

        self.assertEqual(len(first_batch), 1)
        self.assertEqual(first_batch[0]["schedule_time_of_day"], "09:00")
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
