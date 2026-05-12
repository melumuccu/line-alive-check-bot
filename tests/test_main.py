from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException, Request

from line_alive_check_bot import db
from line_alive_check_bot.config import Settings
from line_alive_check_bot.main import (
    list_check_ins,
    create_message_schedule,
    delete_message_schedule,
    get_message_schedule,
    list_message_schedules,
    receive_webhook,
    update_message_schedule,
    MessageScheduleCreateRequest,
    MessageScheduleUpdateRequest,
)


def build_request(body: bytes) -> Request:
    async def receive() -> dict[str, object]:
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/webhook",
            "headers": [],
            "query_string": b"",
        },
        receive,
    )


def build_line_signature(channel_secret: str, body: bytes) -> str:
    return base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")


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


class WebhookApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings = Settings(
            database_path=Path(self.temporary_directory.name) / "app.db",
            line_channel_secret="test-channel-secret",
        )
        db.init_db(self.settings)

    def test_receive_webhook_accepts_valid_postback_event(self) -> None:
        with db.get_connection(self.settings) as connection:
            connection.execute(
                """
                INSERT INTO check_ins(id, schedule_id, scheduled_at, sent_at, replied_at, status)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    42,
                    1,
                    "2026-05-11T09:00",
                    "2026-05-11T09:00:05",
                    None,
                    "pending",
                ),
            )
            connection.commit()

        body = json.dumps(
            {
                "destination": "U1234567890",
                "events": [
                    {
                        "type": "postback",
                        "replyToken": "reply-token",
                        "timestamp": 1715500000000,
                        "source": {"type": "user", "userId": "U1234567890"},
                        "postback": {
                            "data": "action=confirm_check_in&check_in_id=42",
                        },
                    }
                ],
            }
        ).encode("utf-8")
        signature = build_line_signature(self.settings.line_channel_secret or "", body)

        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            response = asyncio.run(receive_webhook(build_request(body), signature))

        self.assertTrue(response.ok)
        self.assertEqual(response.events_received, 1)
        self.assertEqual(response.postback_events_received, 1)

        with db.get_connection(self.settings) as connection:
            stored_check_in = connection.execute(
                """
                SELECT replied_at, status
                FROM check_ins
                WHERE id = ?
                """,
                (42,),
            ).fetchone()

        self.assertIsNotNone(stored_check_in)
        self.assertEqual(stored_check_in["status"], "success")
        self.assertIsNotNone(stored_check_in["replied_at"])

    def test_receive_webhook_logs_event_type_and_source_user_id(self) -> None:
        body = json.dumps(
            {
                "destination": "U1234567890",
                "events": [
                    {
                        "type": "message",
                        "replyToken": "reply-token",
                        "timestamp": 1715500000000,
                        "source": {"type": "user", "userId": "U1234567890"},
                        "message": {"type": "text", "text": "hello"},
                    }
                ],
            }
        ).encode("utf-8")
        signature = build_line_signature(self.settings.line_channel_secret or "", body)

        with (
            patch("line_alive_check_bot.main.get_settings", return_value=self.settings),
            patch("line_alive_check_bot.main.logger") as mock_logger,
        ):
            response = asyncio.run(receive_webhook(build_request(body), signature))

        self.assertTrue(response.ok)
        mock_logger.info.assert_called_once_with(
            "received LINE webhook event type=%s source_type=%s source_user_id=%s",
            "message",
            "user",
            "U1234567890",
        )

    def test_receive_webhook_accepts_valid_verification_request(self) -> None:
        body = json.dumps(
            {
                "destination": "U1234567890",
                "events": [],
            }
        ).encode("utf-8")
        signature = build_line_signature(self.settings.line_channel_secret or "", body)

        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            response = asyncio.run(receive_webhook(build_request(body), signature))

        self.assertTrue(response.ok)
        self.assertEqual(response.events_received, 0)
        self.assertEqual(response.postback_events_received, 0)

    def test_receive_webhook_rejects_invalid_signature(self) -> None:
        body = json.dumps(
            {
                "destination": "U1234567890",
                "events": [],
            }
        ).encode("utf-8")

        with patch("line_alive_check_bot.main.get_settings", return_value=self.settings):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(receive_webhook(build_request(body), "invalid-signature"))

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "invalid LINE signature")
