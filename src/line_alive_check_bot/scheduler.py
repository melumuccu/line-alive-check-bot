from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import get_settings
from .db import init_db, queue_due_check_ins

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [scheduler] %(message)s",
)
logger = logging.getLogger(__name__)


def run_once() -> int:
    settings = get_settings()
    init_db(settings)

    now = datetime.now(ZoneInfo(settings.timezone)).replace(second=0, microsecond=0)
    queued = queue_due_check_ins(settings, now)

    logger.info("checked %s due schedules at %s", len(queued), now.isoformat(timespec="minutes"))
    return len(queued)


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
