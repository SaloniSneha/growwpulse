"""
Scheduler: runs the full Groww Pulse pipeline every N minutes.
Default: every 5 minutes. Configurable via GROWW_SCHEDULER_INTERVAL_MINUTES.
Sends email to fixed recipient on each run.
Logs to data/logs/scheduler.log
"""

import logging
import os
import sys
import time
from datetime import datetime

import schedule
import pytz

# ── Logging setup ──────────────────────────────────────────────────────────
os.makedirs("data/logs", exist_ok=True)

_log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

_file_handler = logging.FileHandler("data/logs/scheduler.log", encoding="utf-8")
_file_handler.setFormatter(_log_formatter)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(_file_handler)
root_logger.addHandler(_stdout_handler)

logger = logging.getLogger("groww_pulse.scheduler")


def run_pipeline_job():
    """Full pipeline job called by the scheduler."""
    from dotenv import load_dotenv
    load_dotenv()

    from groww_pulse.config import (
        SCHEDULER_RECIPIENT, SCHEDULER_WEEKS, SCHEDULER_MAX_REVIEWS
    )

    run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"╔════════════════════════════════════════")
    logger.info(f"║  Scheduler job started at {run_at}")
    logger.info(f"║  Recipient: {SCHEDULER_RECIPIENT}")
    logger.info(f"║  Weeks: {SCHEDULER_WEEKS}, Max Reviews: {SCHEDULER_MAX_REVIEWS}")
    logger.info(f"╚════════════════════════════════════════")

    try:
        from groww_pulse.phase1 import run_phase1
        reviews_path = run_phase1(weeks=SCHEDULER_WEEKS, max_reviews=SCHEDULER_MAX_REVIEWS)

        from groww_pulse.phase2 import run_phase2a, run_phase2b
        themes = run_phase2a(reviews_path=reviews_path)
        grouped_path = run_phase2b(themes=themes, reviews_path=reviews_path)

        from groww_pulse.phase3 import run_phase3
        md_path, txt_path = run_phase3(grouped_path=grouped_path)

        from groww_pulse.phase4 import run_phase4
        eml_path = run_phase4(
            pulse_md_path=md_path,
            recipient=SCHEDULER_RECIPIENT,
            send=True,
        )

        logger.info(f"✅ Scheduler job complete. Email sent to {SCHEDULER_RECIPIENT}")

    except Exception as e:
        logger.error(f"❌ Scheduler job failed: {e}", exc_info=True)


def main():
    from dotenv import load_dotenv
    load_dotenv()

    interval = int(os.getenv("GROWW_SCHEDULER_INTERVAL_MINUTES", "5"))
    tz_name = os.getenv("GROWW_SCHEDULER_TZ", "Asia/Kolkata")

    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.utc

    logger.info(f"🗓️  Scheduler starting — runs every {interval} minute(s) [{tz_name}]")
    logger.info(f"   Log file: data/logs/scheduler.log")

    schedule.every(interval).minutes.do(run_pipeline_job)

    # Run once immediately on start
    logger.info("Running initial job on startup...")
    run_pipeline_job()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
