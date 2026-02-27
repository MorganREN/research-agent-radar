# src/dashboard/database.py
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor

# Add project root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlmodel import Session, select, SQLModel, col
from sqlalchemy import text
from src.research_agent.storage.models import Paper, engine
from src.research_agent.agents.analysis.extracter import PDFUploadParser
from src.research_agent.agents.analysis.reviewer import PaperReviewer
from loguru import logger

# --- Background analysis task management ---
# Status: "running" | "done" | "error"
_analysis_tasks: dict[str, str] = {}
_tasks_lock = threading.Lock()
_analysis_executor = ThreadPoolExecutor(max_workers=3)


def _ensure_columns():
    """Add new columns to existing paper table (SQLite safe, ignore if column exists)."""
    migrations = [
        ("relevance_score", "INTEGER"),
        ("is_bookmarked", "BOOLEAN DEFAULT 0"),
    ]
    # scheduler run table migration
    scheduler_migrations = [
        ("schedulerrun", "pid", "INTEGER"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in migrations:
            try:
                conn.execute(text(f"ALTER TABLE paper ADD COLUMN {col_name} {col_def}"))
                conn.commit()
                logger.info(f"Added column: paper.{col_name}")
            except Exception:
                pass  # column already exists
        for table, col_name, col_def in scheduler_migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
                conn.commit()
                logger.info(f"Added column: {table}.{col_name}")
            except Exception:
                pass  # column already exists


def process_uploaded_pdf(file_path: str) -> dict:
    """Only parse PDF metadata and store in database (no deep analysis)."""
    parser = PDFUploadParser()
    try:
        paper = parser.parse_info(file_path)
        if not paper:
            logger.error("PDF parsing failed, unable to extract paper information.")
            return {"error": "PDF parsing failed, unable to extract paper information."}
        logger.info(f"Paper metadata extraction complete: {paper.title}")
        return {"message": "PDF metadata parsing complete", "paper_id": paper.id}
    except Exception as e:
        logger.error(f"Error processing uploaded PDF: {e}")
        return {"error": f"Error processing uploaded PDF: {e}"}


def _run_analysis_background(paper_id: str, file_path: str):
    """Background thread: execute deep analysis on papers, write to database when complete."""
    try:
        reviewer = PaperReviewer()
        with Session(engine) as session:
            paper = session.get(Paper, paper_id)
            if not paper:
                logger.error(f"Background analysis: Paper {paper_id} not found")
                with _tasks_lock:
                    _analysis_tasks[paper_id] = "error"
                return
            report = reviewer.analyze_paper(paper, pdf_path=file_path)
            paper.analysis_report = report
            session.add(paper)
            session.commit()
            logger.info(f"Background analysis complete: {paper.title}")
        with _tasks_lock:
            _analysis_tasks[paper_id] = "done"
    except Exception as e:
        logger.error(f"Background analysis error ({paper_id}): {e}")
        with _tasks_lock:
            _analysis_tasks[paper_id] = "error"


def start_background_analysis(paper_id: str, file_path: str):
    """Submit paper deep analysis to thread pool (max 3 in parallel)."""
    with _tasks_lock:
        if _analysis_tasks.get(paper_id) == "running":
            return  # Already running
        _analysis_tasks[paper_id] = "running"
    _analysis_executor.submit(_run_analysis_background, paper_id, file_path)


def get_analysis_status(paper_id: str) -> str | None:
    """Query background analysis status: 'running' | 'done' | 'error' | None"""
    with _tasks_lock:
        return _analysis_tasks.get(paper_id)


def clear_analysis_status(paper_id: str):
    """Clear completed/failed task status."""
    with _tasks_lock:
        _analysis_tasks.pop(paper_id, None)


def has_running_tasks() -> bool:
    """Check if there are any running background analysis tasks."""
    with _tasks_lock:
        return any(v == "running" for v in _analysis_tasks.values())


def get_distinct_sources() -> list[str]:
    """Return sorted list of distinct paper source values from the database."""
    try:
        with Session(engine) as session:
            statement = select(Paper.source).distinct()
            results = session.exec(statement).all()
            return sorted(results)
    except Exception as e:
        logger.error(f"Error loading distinct sources: {e}")
        return []


def toggle_bookmark(paper_id: str) -> bool:
    """Toggle paper bookmark status, return new is_bookmarked value."""
    with Session(engine) as session:
        paper = session.get(Paper, paper_id)
        if not paper:
            return False
        paper.is_bookmarked = not paper.is_bookmarked
        session.add(paper)
        session.commit()
        logger.info(f"Bookmark toggled: {paper_id} -> {paper.is_bookmarked}")
        return paper.is_bookmarked


def initialize_database() -> bool:
    """Create all database tables and ensure new columns exist."""
    try:
        SQLModel.metadata.create_all(engine)
        _ensure_columns()
        logger.info("Database tables initialized")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


def check_database_initialized() -> bool:
    """Check if database has papers, indicating it's been initialized"""
    try:
        with Session(engine) as session:
            statement = select(Paper)
            result = session.exec(statement).first()
            return result is not None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False


def load_papers(
    show_only_relevant: bool = True,
    filter_sources: list = None,
    sort_by: str = "date",
    show_bookmarked_only: bool = False,
):
    """Load papers from database with filtering and sorting."""
    try:
        with Session(engine) as session:
            statement = select(Paper)

            if show_only_relevant:
                statement = statement.where(Paper.is_relevant == True)

            if filter_sources:
                statement = statement.where(Paper.source.in_(filter_sources))

            if show_bookmarked_only:
                statement = statement.where(Paper.is_bookmarked == True)

            # Sorting
            if sort_by == "score":
                statement = statement.order_by(
                    col(Paper.relevance_score).desc().nulls_last(),
                    Paper.published_date.desc(),
                )
            else:
                statement = statement.order_by(Paper.published_date.desc())

            papers = session.exec(statement).all()
            logger.info(f"Loaded {len(papers)} papers from database")
            return papers
    except Exception as e:
        logger.error(f"Error loading papers: {e}")
        return []
