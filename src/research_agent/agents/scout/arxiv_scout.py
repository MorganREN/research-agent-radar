# src/research_agent/agents/scout/arxiv_scout.py
import arxiv
from src.research_agent.storage.models import Paper
from datetime import datetime
from loguru import logger

class ArxivScout:
    def __init__(self, query: str = "cat:cs.AI OR cat:cs.CE", max_results: int = 10):
        """
        query: arXiv查询语法。cs.CE 代表 Civil Engineering (土木工程)
        """
        self.query = query
        self.max_results = max_results

    def fetch_papers(self) -> list[Paper]:
        logger.info(f"🕵️ Scout 正在 arXiv 搜索: {self.query} ...")
        
        # 使用 arXiv 客户端搜索
        client = arxiv.Client()
        search = arxiv.Search(
            query=self.query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate # 获取最新的
        )

        papers_found = []
        for result in client.results(search):
            # 将 arXiv 原生对象转换为我们的数据库模型
            paper = Paper(
                id=f"arxiv:{result.entry_id.split('/')[-1]}", # 提取 ID 如 2401.12345
                title=result.title,
                abstract=result.summary.replace("\n", " "),
                authors=[a.name for a in result.authors],
                url=result.pdf_url,
                published_date=result.published,
                source="arxiv",
                is_oa=True,  # arXiv 上的论文都是开放获取的
                doi=result.doi if result.doi else None,  # 有些论文没有 DOI
                full_text_content=None  # arXiv 不存储全文文本
            )
            papers_found.append(paper)

        logger.success(f"✅ Arxiv Scout 找到了 {len(papers_found)} 篇论文。")
        return papers_found