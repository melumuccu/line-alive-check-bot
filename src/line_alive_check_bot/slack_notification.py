from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


class SlackNotificationConfigurationError(RuntimeError):
    pass


class SlackNotificationError(RuntimeError):
    pass


def build_alert_payload(check_in: Mapping[str, object]) -> dict[str, object]:
    return {
        "text": "反応がありません。確認連絡を推奨します。",
    }


def send_alert_notification(settings: Settings, check_in: Mapping[str, object]) -> None:
    if not settings.slack_webhook_url:
        raise SlackNotificationConfigurationError("APP_SLACK_WEBHOOK_URL is not configured")

    payload = build_alert_payload(check_in)
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
