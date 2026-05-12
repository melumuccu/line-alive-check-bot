from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import db
from .config import get_settings
from .line_messaging import (
    LineMessagingConfigurationError,
    LineMessagingError,
    send_check_in_message,
)
from .slack_notification import (
    SlackNotificationConfigurationError,
    SlackNotificationError,
    send_alert_notification,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [scheduler] %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_check_in_timestamp(timestamp_value: str, timezone_name: str) -> datetime | None:
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp_value)
    except ValueError:
        return None

    timezone = ZoneInfo(timezone_name)
    if parsed_timestamp.tzinfo is None:
        return parsed_timestamp.replace(tzinfo=timezone)

    return parsed_timestamp.astimezone(timezone)


def get_alert_after_hours(settings) -> int | None:
    alert_setting = db.get_app_setting(settings, "alert_after_hours")
    if alert_setting is None:
        logger.warning("skipped overdue check-in scan: alert_after_hours is not configured")
        return None

    try:
        return int(alert_setting["value"])
    except ValueError:
        logger.warning(
            "skipped overdue check-in scan: alert_after_hours is invalid value=%s",
            alert_setting["value"],
        )
        return None


def process_overdue_check_ins(settings, now: datetime) -> int:
    alert_after_hours = get_alert_after_hours(settings)
    if alert_after_hours is None:
        return 0

    overdue_before = now - timedelta(hours=alert_after_hours)
    pending_check_ins = db.list_pending_check_ins(settings)
    alerted_count = 0
    notified_count = 0

    for check_in in pending_check_ins:
        sent_at = normalize_check_in_timestamp(str(check_in["sent_at"]), settings.timezone)
        if sent_at is None or sent_at > overdue_before:
            continue

        alerted_check_in = db.mark_check_in_alert(settings, int(check_in["id"]))
        if alerted_check_in is None:
            continue

        alerted_count += 1

        try:
            send_alert_notification(settings, alerted_check_in)
        except SlackNotificationConfigurationError as exc:
            logger.warning("skipped Slack alert for check_in_id=%s: %s", alerted_check_in["id"], exc)
            continue
        except SlackNotificationError:
            logger.exception("failed to send Slack alert for check_in_id=%s", alerted_check_in["id"])
            continue

        notified_count += 1

    logger.info(
        "processed %s overdue check-ins and sent %s Slack alerts at %s",
        alerted_count,
        notified_count,
        now.isoformat(timespec="minutes"),
    )
    return alerted_count


def run_once() -> int:
    settings = get_settings()
    db.init_db(settings)

    now = datetime.now(ZoneInfo(settings.timezone)).replace(second=0, microsecond=0)
    queued_check_ins = db.queue_due_check_ins(settings, now)
    sent_count = 0

    for check_in in queued_check_ins:
        check_in_id = check_in["id"]

        try:
            send_check_in_message(settings, check_in)
        except LineMessagingConfigurationError as exc:
            logger.warning("skipped LINE push for check_in_id=%s: %s", check_in_id, exc)
            continue
        except LineMessagingError:
            logger.exception("failed to send LINE push for check_in_id=%s", check_in_id)
            continue

        sent_at = datetime.now(ZoneInfo(settings.timezone)).replace(microsecond=0)
        db.mark_check_in_sent(settings, check_in_id, sent_at)
        sent_count += 1

    process_overdue_check_ins(settings, now)

    logger.info(
        "processed %s due check-ins and sent %s LINE messages at %s",
        len(queued_check_ins),
        sent_count,
        now.isoformat(timespec="minutes"),
    )
    return sent_count


def run_forever() -> None:
    settings = get_settings()

    while True:
        loop_started = time.monotonic()
        run_once()
        elapsed = time.monotonic() - loop_started
        sleep_seconds = max(1, settings.scheduler_poll_seconds - elapsed)
        time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the alive-check scheduler worker")
    parser.add_argument("--once", action="store_true", help="Run one scheduler cycle and exit")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    run_forever()


if __name__ == "__main__":
    main()
