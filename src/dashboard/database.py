# src/dashboard/database.py
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlmodel import Session, select, SQLModel, col
from sqlalchemy import text
from src.research_agent.storage.models import Paper, engine
from src.research_agent.agents.analysis.extracter import PDFUploadParser
from src.research_agent.agents.analysis.reviewer import PaperReviewer
from loguru import logger

# --- 后台分析任务管理 ---
# 状态: "running" | "done" | "error"
_analysis_tasks: dict[str, str] = {}
_tasks_lock = threading.Lock()
_analysis_executor = ThreadPoolExecutor(max_workers=3)


def _ensure_columns():
    """为已有的 paper 表添加新增列（SQLite 安全，列已存在时忽略）。"""
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
    """仅解析 PDF 元数据并存入数据库（不执行深度分析）。"""
    parser = PDFUploadParser()
    try:
        paper = parser.parse_info(file_path)
        if not paper:
            logger.error("PDF 解析失败，无法提取论文信息。")
            return {"error": "PDF 解析失败，无法提取论文信息。"}
        logger.info(f"论文元数据提取完成: {paper.title}")
        return {"message": "PDF 元数据解析完成", "paper_id": paper.id}
    except Exception as e:
        logger.error(f"处理上传 PDF 时出错: {e}")
        return {"error": f"处理上传 PDF 时出错: {e}"}


def _run_analysis_background(paper_id: str, file_path: str):
    """后台线程：对论文执行深度分析，完成后写入数据库。"""
    try:
        reviewer = PaperReviewer()
        with Session(engine) as session:
            paper = session.get(Paper, paper_id)
            if not paper:
                logger.error(f"后台分析: 论文 {paper_id} 不存在")
                with _tasks_lock:
                    _analysis_tasks[paper_id] = "error"
                return
            report = reviewer.analyze_paper(paper, pdf_path=file_path)
            paper.analysis_report = report
            session.add(paper)
            session.commit()
            logger.info(f"后台分析完成: {paper.title}")
        with _tasks_lock:
            _analysis_tasks[paper_id] = "done"
    except Exception as e:
        logger.error(f"后台分析出错 ({paper_id}): {e}")
        with _tasks_lock:
            _analysis_tasks[paper_id] = "error"


def start_background_analysis(paper_id: str, file_path: str):
    """提交论文深度分析到线程池（最多 3 篇并行）。"""
    with _tasks_lock:
        if _analysis_tasks.get(paper_id) == "running":
            return  # 已在运行
        _analysis_tasks[paper_id] = "running"
    _analysis_executor.submit(_run_analysis_background, paper_id, file_path)


def get_analysis_status(paper_id: str) -> str | None:
    """查询后台分析状态: 'running' | 'done' | 'error' | None"""
    with _tasks_lock:
        return _analysis_tasks.get(paper_id)


def clear_analysis_status(paper_id: str):
    """清除已完成/失败的任务状态。"""
    with _tasks_lock:
        _analysis_tasks.pop(paper_id, None)


def has_running_tasks() -> bool:
    """是否有正在运行的后台分析任务。"""
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
    """切换论文的收藏状态，返回新的 is_bookmarked 值。"""
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

            # 排序
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
