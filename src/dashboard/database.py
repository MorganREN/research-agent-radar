# src/dashboard/database.py
import sys
import os

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlmodel import Session, select, SQLModel
from src.research_agent.storage.models import Paper, engine
from src.research_agent.agents.analysis.extracter import PDFUploadParser
from src.research_agent.agents.analysis.reviewer import PaperReviewer
from loguru import logger

def process_uploaded_pdf(file_path: str) -> dict:
    parser = PDFUploadParser()
    reviewer = PaperReviewer()
    try:
        paper = parser.parse_info(file_path)
        if not paper:
            logger.error("PDF 解析失败，无法提取论文信息。")
            return {"error": "PDF 解析失败，无法提取论文信息。"}
        # 这里可以直接调用 reviewer 进行分析，生成初步的分析报告
        analysis_report = reviewer.analyze_paper(paper, pdf_path=file_path)
        paper.analysis_report = analysis_report
        logger.info(f"✅ 论文分析完成: {paper.title}")
        # 将解析和分析结果存储到数据库中
        parser.refresh_database(paper)
        return {"message": "PDF 解析和分析完成，并已存储到数据库。", "paper_id": paper.id}
    except Exception as e:
        logger.error(f"处理上传 PDF 时出错: {e}")
        return {"error": f"处理上传 PDF 时出错: {e}"}

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
                # Assuming Paper model has a 'source' field
                statement = statement.where(Paper.source.in_(filter_sources))
            
            papers = session.exec(statement).all()
            logger.info(f"✅ Loaded {len(papers)} papers from database")
            return papers
    except Exception as e:
        logger.error(f"Error loading papers: {e}")
        return []