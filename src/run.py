# src/run.py
"""
Production entry point for Research Agent Radar.

Usage:
    poetry run radar              # Start the scheduler daemon
    poetry run radar --once       # Run the pipeline once and exit
    python src/run.py             # Same as above (direct execution)
    python src/run.py --once
"""
import sys
import os
import argparse
import signal
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Ensure project root is on sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger

from src.research_agent.storage.models import create_db_and_tables
from src.research_agent.scheduler.runner import run_pipeline_from_config, _load_user_config
from src.research_agent.scheduler.status import update_scheduler_state

BRISBANE_TZ = ZoneInfo("Australia/Brisbane")


def _next_scheduled_time(hour: int = 5, minute: int = 0) -> datetime:
    """Return the next occurrence of HH:MM Brisbane time (AEST, UTC+10) as a timezone-aware datetime."""
    now_brisbane = datetime.now(BRISBANE_TZ)
    target = now_brisbane.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_brisbane >= target:
        target += timedelta(days=1)
    return target


def main():
    parser = argparse.ArgumentParser(
        description="Research Agent Radar - Automated Paper Discovery Scheduler"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit (no scheduling)",
    )
    args = parser.parse_args()

    # Ensure DB tables exist (including scheduler tables)
    create_db_and_tables()

    if args.once:
        logger.info("Running pipeline once (manual trigger)...")
        try:
            run_pipeline_from_config(trigger="manual")
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            sys.exit(1)
        return

    # --- Daemon mode: recurring scheduled runs ---
    config = _load_user_config()
    scheduled_time_str = config.get("scheduled_time", "08:00")
    hour, minute = (int(x) for x in scheduled_time_str.split(":"))
    frequency_str = f"Daily at {scheduled_time_str} AEST (Brisbane)"

    stop_event = threading.Event()

    def shutdown(signum, frame):
        logger.info("Received shutdown signal, stopping scheduler...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Register scheduler state
    update_scheduler_state(
        is_running=True,
        pid=os.getpid(),
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        next_run_at=datetime.now(timezone.utc).replace(tzinfo=None),
        frequency=frequency_str,
    )

    logger.info(
        f"Scheduler started (PID={os.getpid()}, schedule={frequency_str}). "
        f"Press Ctrl+C to stop."
    )

    try:
        while not stop_event.is_set():
            try:
                run_pipeline_from_config(trigger="scheduled")
            except Exception as e:
                logger.error(f"Pipeline run failed: {e}")

            next_brisbane = _next_scheduled_time(hour, minute)
            wait_seconds = (next_brisbane - datetime.now(BRISBANE_TZ)).total_seconds()
            # Store next_run as naive UTC for dashboard display
            next_run_utc = next_brisbane.astimezone(timezone.utc).replace(tzinfo=None)
            update_scheduler_state(
                is_running=True,
                pid=os.getpid(),
                next_run_at=next_run_utc,
                frequency=frequency_str,
            )
            logger.info(f"Next run scheduled at {next_brisbane.strftime('%Y-%m-%d %H:%M')} AEST (Brisbane)")

            # Wait until the scheduled time or until stop signal
            stop_event.wait(timeout=wait_seconds)
    finally:
        update_scheduler_state(is_running=False, pid=None)
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
