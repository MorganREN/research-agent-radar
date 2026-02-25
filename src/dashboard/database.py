# src/dashboard/database.py
import sys
import os
import threading

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlmodel import Session, select, SQLModel
from src.research_agent.storage.models import Paper, engine
from src.research_agent.agents.analysis.extracter import PDFUploadParser
from src.research_agent.agents.analysis.reviewer import PaperReviewer
from loguru import logger

# --- 后台分析任务管理 ---
# 状态: "running" | "done" | "error"
_analysis_tasks: dict[str, str] = {}
_tasks_lock = threading.Lock()


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
    """启动后台线程执行论文深度分析。"""
    with _tasks_lock:
        if _analysis_tasks.get(paper_id) == "running":
            return  # 已在运行
        _analysis_tasks[paper_id] = "running"
    t = threading.Thread(
        target=_run_analysis_background,
        args=(paper_id, file_path),
        daemon=True,
    )
    t.start()


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


def initialize_database() -> bool:
    """Create all database tables"""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("✅ Database tables initialized")
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
            is_initialized = result is not None
            status = "✅ Database initialized with data" if is_initialized else "⚠️ Database empty"
            logger.info(status)
            return is_initialized
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False

def load_papers(show_only_relevant: bool = True, filter_sources: list = None):
    """Load papers from database with optional filtering"""
    try:
        with Session(engine) as session:
            statement = select(Paper).order_by(Paper.published_date.desc())

            if show_only_relevant:
                statement = statement.where(Paper.is_relevant == True)

            # Add source filtering if provided
            if filter_sources:
                statement = statement.where(Paper.source.in_(filter_sources))

            papers = session.exec(statement).all()
            logger.info(f"✅ Loaded {len(papers)} papers from database")
            return papers
    except Exception as e:
        logger.error(f"Error loading papers: {e}")
        return []
