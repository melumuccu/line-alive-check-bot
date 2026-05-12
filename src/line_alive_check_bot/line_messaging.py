from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen

from .config import Settings


class LineMessagingConfigurationError(RuntimeError):
    pass


class LineMessagingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LinePostbackEvent:
    reply_token: str | None
    data: str
    data_params: dict[str, str]
    source_user_id: str | None
    timestamp: int | None


def build_check_in_postback_data(check_in_id: int) -> str:
    return urlencode(
        {
            "action": "confirm_check_in",
            "check_in_id": str(check_in_id),
        }
    )


def validate_webhook_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    expected_signature = b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature.strip())


def parse_postback_data(data: str) -> dict[str, str]:
    return dict(parse_qsl(data, keep_blank_values=True))


def extract_postback_events(payload: Mapping[str, object]) -> list[LinePostbackEvent]:
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        return []

    postback_events: list[LinePostbackEvent] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping) or raw_event.get("type") != "postback":
            continue

        raw_postback = raw_event.get("postback")
        if not isinstance(raw_postback, Mapping):
            continue

        data = raw_postback.get("data")
        if not isinstance(data, str):
            continue

        reply_token = raw_event.get("replyToken")
        raw_source = raw_event.get("source")
        source_user_id: str | None = None
        if isinstance(raw_source, Mapping):
            raw_user_id = raw_source.get("userId")
            if isinstance(raw_user_id, str):
                source_user_id = raw_user_id

        raw_timestamp = raw_event.get("timestamp")
        timestamp = raw_timestamp if isinstance(raw_timestamp, int) else None
        postback_events.append(
            LinePostbackEvent(
                reply_token=reply_token if isinstance(reply_token, str) else None,
                data=data,
                data_params=parse_postback_data(data),
                source_user_id=source_user_id,
                timestamp=timestamp,
            )
        )

    return postback_events


def format_scheduled_at(scheduled_at_value: str) -> str:
    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_value)
    except ValueError:
        return scheduled_at_value

    return scheduled_at.strftime("%Y/%m/%d %H:%M")


def build_check_in_flex_message(check_in: Mapping[str, object]) -> dict[str, object]:
    check_in_id = int(check_in["id"])
    schedule_label = str(check_in["schedule_label"])
    scheduled_at = format_scheduled_at(str(check_in["scheduled_at"]))
    alt_text = f"{schedule_label}の安否確認です。確認したら「無事です」を押してください。"

    return {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "安否確認",
                        "weight": "bold",
                        "size": "xl",
                    },
                    {
                        "type": "text",
                        "text": f"{schedule_label}の確認です。",
                        "size": "md",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": f"送信予定: {scheduled_at}",
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": "このメッセージを確認したら、下のボタンを押してください。",
                        "size": "sm",
                        "wrap": True,
                        "color": "#666666",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#2E7D32",
                        "action": {
                            "type": "postback",
                            "label": "無事です",
                            "data": build_check_in_postback_data(check_in_id),
                            "displayText": "無事です",
                        },
                    }
                ],
            },
        },
    }


def send_check_in_message(settings: Settings, check_in: Mapping[str, object]) -> None:
    if not settings.line_channel_access_token:
        raise LineMessagingConfigurationError("APP_LINE_CHANNEL_ACCESS_TOKEN is not configured")

    if not settings.line_user_id:
        raise LineMessagingConfigurationError("APP_LINE_USER_ID is not configured")

    payload = {
        "to": settings.line_user_id,
        "messages": [build_check_in_flex_message(check_in)],
    }
    request = Request(
        url=f"{settings.line_api_base_url.rstrip('/')}/v2/bot/message/push",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.line_channel_access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            response.read()
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise LineMessagingError(
            f"LINE push message failed with status {exc.code}: {response_body}"
        ) from exc
    except URLError as exc:
        raise LineMessagingError(f"LINE push message failed: {exc.reason}") from exc