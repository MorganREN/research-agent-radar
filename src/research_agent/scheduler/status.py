# src/research_agent/scheduler/status.py
import os
import signal
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select
from loguru import logger

from src.research_agent.storage.models import (
    SchedulerState, SchedulerRun, engine,
)


def update_scheduler_state(
    is_running: bool,
    pid: Optional[int] = None,
    started_at: Optional[datetime] = None,
    next_run_at: Optional[datetime] = None,
    frequency: Optional[str] = None,
) -> None:
    """Upsert the singleton SchedulerState row."""
    with Session(engine) as session:
        state = session.get(SchedulerState, 1)
        if state is None:
            state = SchedulerState(id=1)
        state.is_running = is_running
        state.pid = pid
        if started_at is not None:
            state.started_at = started_at
        if next_run_at is not None:
            state.next_run_at = next_run_at
        if frequency is not None:
            state.update_frequency = frequency
        if not is_running:
            state.next_run_at = None
        session.add(state)
        session.commit()


def get_scheduler_state() -> Optional[SchedulerState]:
    """Read the current scheduler state."""
    with Session(engine) as session:
        return session.get(SchedulerState, 1)


def is_scheduler_alive() -> bool:
    """Check if the scheduler process is actually running (PID check)."""
    state = get_scheduler_state()
    if state is None or not state.is_running or state.pid is None:
        return False
    try:
        os.kill(state.pid, 0)  # signal 0: no-op, just check existence
        return True
    except (ProcessLookupError, PermissionError):
        return False


def create_run(trigger: str = "scheduled") -> SchedulerRun:
    """Insert a new run record with status 'running'."""
    run = SchedulerRun(
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status="running",
        pid=os.getpid(),
        trigger=trigger,
    )
    with Session(engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        logger.info(f"Pipeline run #{run.id} started (trigger={trigger})")
        return run


def complete_run(
    run_id: int,
    papers_found: int = 0,
    papers_relevant: int = 0,
    papers_analyzed: int = 0,
) -> None:
    """Mark a run as completed."""
    with Session(engine) as session:
        run = session.get(SchedulerRun, run_id)
        if run is None:
            return
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.papers_found = papers_found
        run.papers_relevant = papers_relevant
        run.papers_analyzed = papers_analyzed
        session.add(run)
        session.commit()
        logger.info(
            f"Pipeline run #{run_id} completed: "
            f"found={papers_found}, relevant={papers_relevant}, analyzed={papers_analyzed}"
        )


def fail_run(run_id: int, error_message: str) -> None:
    """Mark a run as failed."""
    with Session(engine) as session:
        run = session.get(SchedulerRun, run_id)
        if run is None:
            return
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.error_message = error_message
        session.add(run)
        session.commit()
        logger.error(f"Pipeline run #{run_id} failed: {error_message}")


def get_recent_runs(limit: int = 20) -> list[SchedulerRun]:
    """Return recent run history, newest first."""
    with Session(engine) as session:
        statement = (
            select(SchedulerRun)
            .order_by(SchedulerRun.started_at.desc())
            .limit(limit)
        )
        return list(session.exec(statement).all())


def stop_run(run_id: int) -> bool:
    """Terminate a running pipeline process by its run ID.

    Sends SIGTERM to the process, then marks the run as failed.
    Returns True if the process was successfully signalled.
    """
    with Session(engine) as session:
        run = session.get(SchedulerRun, run_id)
        if run is None or run.status != "running" or run.pid is None:
            return False

        pid = run.pid
        killed = False
        try:
            os.kill(pid, signal.SIGTERM)
            killed = True
            logger.info(f"Sent SIGTERM to pipeline process PID={pid} (run #{run_id})")
        except ProcessLookupError:
            logger.warning(f"Process PID={pid} already exited (run #{run_id})")
            killed = True  # process is gone, still mark as stopped
        except PermissionError:
            logger.error(f"No permission to kill PID={pid} (run #{run_id})")
            return False

        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.error_message = "Manually stopped by user"
        session.add(run)
        session.commit()
        return killed
