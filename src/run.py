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
from datetime import datetime, timedelta

# Ensure project root is on sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from loguru import logger

from src.research_agent.storage.models import create_db_and_tables
from src.research_agent.scheduler.runner import run_pipeline_from_config, _load_user_config
from src.research_agent.scheduler.status import update_scheduler_state


FREQUENCY_MAP = {
    "Every 6 hours": timedelta(hours=6),
    "Every 12 hours": timedelta(hours=12),
    "Every 24 hours": timedelta(hours=24),
    "Weekly": timedelta(weeks=1),
}


def parse_frequency(freq_str: str) -> timedelta:
    """Convert config frequency string to timedelta."""
    return FREQUENCY_MAP.get(freq_str, timedelta(hours=24))


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
    frequency_str = config.get("update_frequency", "Every 24 hours")
    interval = parse_frequency(frequency_str)

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
        started_at=datetime.utcnow(),
        next_run_at=datetime.utcnow(),
        frequency=frequency_str,
    )

    logger.info(
        f"Scheduler started (PID={os.getpid()}, frequency={frequency_str}). "
        f"Press Ctrl+C to stop."
    )

    try:
        while not stop_event.is_set():
            try:
                run_pipeline_from_config(trigger="scheduled")
            except Exception as e:
                logger.error(f"Pipeline run failed: {e}")

            next_run = datetime.utcnow() + interval
            update_scheduler_state(
                is_running=True,
                pid=os.getpid(),
                next_run_at=next_run,
                frequency=frequency_str,
            )
            logger.info(f"Next run scheduled at {next_run.strftime('%Y-%m-%d %H:%M UTC')}")

            # Wait for the interval or until stop signal
            stop_event.wait(timeout=interval.total_seconds())
    finally:
        update_scheduler_state(is_running=False, pid=None)
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
