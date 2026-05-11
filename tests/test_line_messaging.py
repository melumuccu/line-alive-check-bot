from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from line_alive_check_bot.config import Settings
from line_alive_check_bot.line_messaging import (
    build_check_in_flex_message,
    build_check_in_postback_data,
    send_check_in_message,
)


class DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"{}"


class LineMessagingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(
            database_path=Path(self.temporary_directory.name) / "app.db",
            line_channel_access_token="test-access-token",
            line_user_id="U1234567890",
        )
        self.check_in = {
            "id": 42,
            "schedule_id": 1,
            "schedule_label": "朝",
            "schedule_time_of_day": "09:00",
            "scheduled_at": "2026-05-11T09:00+09:00",
            "sent_at": None,
            "replied_at": None,
            "status": "pending",
        }

    def test_build_check_in_postback_data_contains_action_and_check_in_id(self) -> None:
        self.assertEqual(
            build_check_in_postback_data(42),
            "action=confirm_check_in&check_in_id=42",
        )

    def test_build_check_in_flex_message_contains_postback_button(self) -> None:
        message = build_check_in_flex_message(self.check_in)

        self.assertEqual(message["type"], "flex")
        self.assertIn("朝の安否確認", message["altText"])
        self.assertEqual(message["contents"]["type"], "bubble")

        button_action = message["contents"]["footer"]["contents"][0]["action"]
        self.assertEqual(button_action["type"], "postback")
        self.assertEqual(button_action["label"], "無事です")
        self.assertEqual(button_action["data"], "action=confirm_check_in&check_in_id=42")

    def test_send_check_in_message_posts_line_push_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return DummyResponse()

        with patch("line_alive_check_bot.line_messaging.urlopen", side_effect=fake_urlopen):
            send_check_in_message(self.settings, self.check_in)

        request = captured["request"]
        self.assertEqual(captured["timeout"], 10)
        self.assertEqual(request.full_url, "https://api.line.me/v2/bot/message/push")

        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["to"], "U1234567890")
        self.assertEqual(payload["messages"][0]["type"], "flex")
