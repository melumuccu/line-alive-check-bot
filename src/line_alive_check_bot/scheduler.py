from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import db
from .config import get_settings
from .line_messaging import (
    LineMessagingConfigurationError,
    LineMessagingError,
    send_check_in_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [scheduler] %(message)s",
)
logger = logging.getLogger(__name__)


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
