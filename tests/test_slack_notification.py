from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from line_alive_check_bot.config import Settings
from line_alive_check_bot.slack_notification import build_alert_payload, send_alert_notification


class DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"ok"


class SlackNotificationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.settings = Settings(
            database_path=Path(temporary_directory.name) / "app.db",
            slack_webhook_url="https://hooks.slack.test/services/abc",
        )
        self.check_in = {
            "id": 42,
            "schedule_id": 1,
            "schedule_label": "朝",
            "schedule_time_of_day": "08:00",
            "scheduled_at": "2026-05-11T08:00:00",
            "sent_at": "2026-05-11T08:00:05",
            "replied_at": None,
            "status": "alert",
        }

    def test_build_alert_payload_contains_requested_text_only(self) -> None:
        payload = build_alert_payload(self.check_in)

        self.assertEqual(payload, {"text": "反応がありません。確認連絡を推奨します。"})

    def test_send_alert_notification_posts_text_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return DummyResponse()

        with patch("line_alive_check_bot.slack_notification.urlopen", side_effect=fake_urlopen):
            send_alert_notification(self.settings, self.check_in)

        request = captured["request"]
        self.assertEqual(captured["timeout"], 10)
        self.assertEqual(request.full_url, "https://hooks.slack.test/services/abc")

        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"text": "反応がありません。確認連絡を推奨します。"})