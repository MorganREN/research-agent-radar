# src/research_agent/storage/models.py
from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON, create_engine

class Paper(SQLModel, table=True):
    # 使用 arXiv ID 作为主键，天然去重
    id: str = Field(primary_key=True)
    
    # 基础元数据
    title: str
    abstract: str
    authors: List[str] = Field(default=[], sa_type=JSON)
    url: str
    published_date: datetime
    source: str = "arxiv"
    is_oa: Optional[bool] = None  # 是否开放获取
    doi: Optional[str] = None      # DOI 号，如果有的话
    full_text_content: Optional[str] = None  # elsevier可能存储全文文本
    
    # 系统状态 (Data Ingestion 核心字段)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 筛选结果
    is_relevant: Optional[bool] = None  # True/False/None(未处理)
    relevance_reason: Optional[str] = None # LLM 给出的理由
    
    # 后续阶段的状态预留
    download_status: str = "pending"
    analysis_report: Optional[str] = None  # LLM 生成的分析报告

# 创建一个本地 SQLite 数据库用于测试
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)