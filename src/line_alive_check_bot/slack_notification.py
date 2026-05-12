from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


class SlackNotificationConfigurationError(RuntimeError):
    pass


class SlackNotificationError(RuntimeError):
    pass


def format_timestamp(timestamp_value: str | None) -> str:
    if not timestamp_value:
        return "不明"

    try:
        timestamp = datetime.fromisoformat(timestamp_value)
    except ValueError:
        return timestamp_value

    return timestamp.strftime("%Y/%m/%d %H:%M")


def build_alert_text(check_in: Mapping[str, object]) -> str:
    schedule_label = str(check_in["schedule_label"])
    schedule_time_of_day = str(check_in["schedule_time_of_day"])
    scheduled_at = format_timestamp(str(check_in["scheduled_at"]))
    sent_at = format_timestamp(str(check_in["sent_at"]))

    return "\n".join(
        [
            "【至急】安否確認の返信がありません",
            f"check_in_id: {check_in['id']}",
            f"スケジュール: {schedule_label} ({schedule_time_of_day})",
            f"送信予定: {scheduled_at}",
            f"送信時刻: {sent_at}",
        ]
    )


def send_alert_notification(settings: Settings, check_in: Mapping[str, object]) -> None:
    if not settings.slack_webhook_url:
        raise SlackNotificationConfigurationError("APP_SLACK_WEBHOOK_URL is not configured")

    payload = {
        "text": build_alert_text(check_in),
    }
    request = Request(
        url=settings.slack_webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise SlackNotificationError(
            f"Slack notification failed with status {exc.code}: {response_body}"
        ) from exc
    except URLError as exc:
        raise SlackNotificationError(f"Slack notification failed: {exc.reason}") from exc
