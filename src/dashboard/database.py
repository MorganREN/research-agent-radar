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
        result = parser.parse_info(file_path)
        # 防御性检查：确保返回的是 Paper 对象而非其他类型
        if result is None:
            logger.error(f"PDF parsing returned None for: {file_path}")
            return {"error": "PDF 解析失败：无法提取论文信息。请确认文件是有效的学术论文 PDF（非扫描版）。"}
        if not isinstance(result, Paper):
            logger.error(f"parse_info returned unexpected type {type(result)}: {result}")
            return {"error": "PDF 解析返回了异常结果，请重试。"}
        logger.info(f"Paper metadata extraction complete: {result.title}")
        return {"message": "PDF metadata parsing complete", "paper_id": result.id}
    except Exception as e:
        logger.error(f"Error processing uploaded PDF: {e}", exc_info=True)
        return {"error": f"处理 PDF 时出错: {e}"}


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


def delete_paper(paper_id: str) -> bool:
    """Delete one paper by id. Returns True if deleted."""
    with Session(engine) as session:
        paper = session.get(Paper, paper_id)
        if not paper:
            return False
        session.delete(paper)
        session.commit()

    with _tasks_lock:
        _analysis_tasks.pop(paper_id, None)

    logger.info(f"Deleted paper: {paper_id}")
    return True


def delete_papers(paper_ids: list[str]) -> int:
    """Delete multiple papers by ids. Returns deleted count."""
    if not paper_ids:
        return 0

    unique_ids = list(dict.fromkeys(paper_ids))
    deleted_count = 0

    with Session(engine) as session:
        for paper_id in unique_ids:
            paper = session.get(Paper, paper_id)
            if not paper:
                continue
            session.delete(paper)
            deleted_count += 1
        session.commit()

    with _tasks_lock:
        for paper_id in unique_ids:
            _analysis_tasks.pop(paper_id, None)

    logger.info(f"Bulk deleted papers: {deleted_count}/{len(unique_ids)}")
    return deleted_count


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
    min_score: int = 0,
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

            if min_score > 0:
                statement = statement.where(
                    col(Paper.relevance_score) >= min_score
                )

            # Sorting
            if sort_by == "score":
                statement = statement.order_by(
                    col(Paper.relevance_score).desc().nulls_last(),
                    Paper.fetched_date.desc().nulls_last(),
                )
            else:
                statement = statement.order_by(Paper.fetched_date.desc().nulls_last())

            papers = session.exec(statement).all()
            logger.info(f"Loaded {len(papers)} papers from database")
            return papers
    except Exception as e:
        logger.error(f"Error loading papers: {e}")
        return []


def load_all_papers() -> list:
    """加载所有论文，按 fetched_date 降序排列。"""
    try:
        with Session(engine) as session:
            statement = select(Paper).order_by(
                Paper.fetched_date.desc().nulls_last()
            )
            return session.exec(statement).all()
    except Exception as e:
        logger.error(f"Error loading all papers: {e}")
        return []
