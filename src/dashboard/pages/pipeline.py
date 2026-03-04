# src/dashboard/pages/pipeline.py
"""Pipeline — Monitor and control the automated paper discovery pipeline."""
import sys
import os
import time
import subprocess

# ban all warnings in this file since it's a dashboard page
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st
from datetime import datetime, timezone

from src.research_agent.storage.models import create_db_and_tables
from src.research_agent.scheduler.status import (
    get_scheduler_state,
    is_scheduler_alive,
    get_recent_runs,
    stop_run,
)

# Ensure tables exist
create_db_and_tables()

# ============================
# Pipeline 专用样式
# ============================
st.markdown("""
<style>
    .status-card {
        padding: 1.25rem 1.5rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    .status-running {
        background: #F0F5EF;
        border-left: 3px solid #3D7A5F;
    }
    .status-stopped {
        background: #FDF6E3;
        border-left: 3px solid #B8860B;
    }
    .status-dead {
        background: #F9EEEE;
        border-left: 3px solid #A63D40;
    }

    .run-row {
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        border: 1px solid #E5E2DC;
        background: #FAF8F5;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    .run-status-completed { border-left: 3px solid #3D7A5F; }
    .run-status-running   { border-left: 3px solid #B8860B; }
    .run-status-failed    { border-left: 3px solid #A63D40; }
</style>
""", unsafe_allow_html=True)

st.markdown("## Pipeline")
st.caption("Monitor and control the automated paper discovery pipeline")

# ============================
# Section 1: Scheduler Status
# ============================
st.markdown("### Status")

state = get_scheduler_state()
alive = is_scheduler_alive()

if state and alive:
    st.markdown(
        '<div class="status-card status-running">'
        '<strong style="color:#3D7A5F;font-size:1.1rem;">RUNNING</strong>'
        '</div>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Frequency", state.update_frequency)
    with col2:
        if state.next_run_at:
            st.metric("Next Run", state.next_run_at.strftime("%Y-%m-%d %H:%M UTC"))
        else:
            st.metric("Next Run", "Running now...")
    with col3:
        st.metric("PID", str(state.pid))

elif state and state.is_running and not alive:
    # PID stale — scheduler crashed
    st.markdown(
        '<div class="status-card status-dead">'
        '<strong style="color:#A63D40;font-size:1.1rem;">STOPPED UNEXPECTEDLY</strong>'
        '<br><span style="color:#6B6B73;font-size:0.85rem;">'
        'The scheduler process is no longer running. Restart with: <code>poetry run radar</code>'
        '</span></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-card status-stopped">'
        '<strong style="color:#8B4513;font-size:1.1rem;">STOPPED</strong>'
        '<br><span style="color:#6B6B73;font-size:0.85rem;">'
        'Start with: <code>poetry run radar</code>'
        '</span></div>',
        unsafe_allow_html=True,
    )

st.divider()

# ============================
# Section 2: Manual Trigger
# ============================
st.markdown("### Manual Run")
st.caption("Trigger a one-shot pipeline run without starting the daemon scheduler")

# Check if there's a running task
latest_runs = get_recent_runs(limit=1)
has_running_run = latest_runs and latest_runs[0].status == "running"

col_start, col_stop, col_info = st.columns([1, 1, 2])
with col_start:
    start_disabled = has_running_run
    if st.button(
        "Run Pipeline Now",
        type="primary",
        use_container_width=True,
        disabled=start_disabled,
    ):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        subprocess.Popen(
            [sys.executable, os.path.join(project_root, "src/run.py"), "--once"],
            cwd=project_root,
        )
        st.toast("Pipeline started in background!")
        time.sleep(2)
        st.rerun()

with col_stop:
    stop_disabled = not has_running_run
    if st.button(
        "Stop Running Task",
        type="secondary",
        use_container_width=True,
        disabled=stop_disabled,
    ):
        if has_running_run:
            success = stop_run(latest_runs[0].id)
            if success:
                st.toast("Task stopped.")
            else:
                st.toast("Failed to stop the task.")
            time.sleep(1)
            st.rerun()

with col_info:
    if has_running_run:
        elapsed = datetime.now(timezone.utc).replace(tzinfo=None) - latest_runs[0].started_at
        mins = int(elapsed.total_seconds() // 60)
        secs = int(elapsed.total_seconds() % 60)
        st.warning(f"A pipeline run is in progress ({mins}m {secs}s elapsed)...")

st.divider()

# ============================
# Section 3: Execution History
# ============================
st.markdown("### Execution History")

runs = get_recent_runs(limit=20)

if not runs:
    st.info("No execution history yet. Run the pipeline to see results here.")
else:
    for run in runs:
        # Status icon and color
        if run.status == "completed":
            icon = "&#10003;"
            css_class = "run-status-completed"
        elif run.status == "running":
            icon = "&#9679;"
            css_class = "run-status-running"
        else:
            icon = "&#10007;"
            css_class = "run-status-failed"

        # Duration
        if run.completed_at and run.started_at:
            duration = run.completed_at - run.started_at
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            duration_str = f"{minutes}m {seconds}s"
        elif run.status == "running":
            elapsed = datetime.now(timezone.utc).replace(tzinfo=None) - run.started_at
            minutes = int(elapsed.total_seconds() // 60)
            seconds = int(elapsed.total_seconds() % 60)
            duration_str = f"{minutes}m {seconds}s (running)"
        else:
            duration_str = "-"

        # Trigger label
        trigger_label = "Manual" if run.trigger == "manual" else "Scheduled"

        # Build row HTML
        started_str = run.started_at.strftime("%Y-%m-%d %H:%M")
        stats_html = (
            f'<span style="color:#6B6B73;font-size:0.82rem;">'
            f'Found: <strong>{run.papers_found}</strong> &nbsp;|&nbsp; '
            f'Relevant: <strong>{run.papers_relevant}</strong> &nbsp;|&nbsp; '
            f'Analyzed: <strong>{run.papers_analyzed}</strong>'
            f'</span>'
        )
        error_html = ""
        if run.error_message:
            error_html = (
                f'<br><span style="color:#A63D40;font-size:0.8rem;">'
                f'Error: {run.error_message[:200]}</span>'
            )

        st.markdown(
            f'<div class="run-row {css_class}">'
            f'<span style="font-size:0.9rem;">{icon} <strong>{started_str}</strong>'
            f' &nbsp;·&nbsp; {trigger_label}'
            f' &nbsp;·&nbsp; {duration_str}</span>'
            f'<br>{stats_html}'
            f'{error_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ============================
# Auto-refresh while a run is in progress
# ============================
if runs and runs[0].status == "running":
    time.sleep(10)
    st.rerun()
