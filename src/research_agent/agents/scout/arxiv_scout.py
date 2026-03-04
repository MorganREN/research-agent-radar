# src/research_agent/agents/scout/arxiv_scout.py
import arxiv
from src.research_agent.storage.models import Paper
from datetime import datetime, timedelta
from loguru import logger


class ArxivScout:
    def __init__(
        self,
        query: str = "cat:cs.AI OR cat:cs.CE",
        days_back: int = 7,
        max_results: int = 200,
    ):
        """
        query: arXiv查询语法。cs.CE 代表 Civil Engineering (土木工程)
        days_back: 搜索最近 N 天内提交的论文
        max_results: 安全上限，防止结果过多
        """
        self.query = query
        self.days_back = days_back
        self.max_results = max_results

    def _build_date_query(self) -> str:
        """将日期范围拼接到查询中，使用 arXiv submittedDate 语法。"""
        end = datetime.utcnow()
        start = end - timedelta(days=self.days_back)
        start_str = start.strftime("%Y%m%d") + "000000"
        end_str = end.strftime("%Y%m%d") + "235959"
        date_filter = f"submittedDate:[{start_str} TO {end_str}]"
        return f"({self.query}) AND {date_filter}"

    def fetch_papers(self) -> list[Paper]:
        full_query = self._build_date_query()
        logger.info(
            f"Scout searching arXiv (last {self.days_back} days): {full_query}"
        )

        client = arxiv.Client()
        search = arxiv.Search(
            query=full_query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        now = datetime.utcnow()
        papers_found = []
        for result in client.results(search):
            # 将 arXiv 原生对象转换为我们的数据库模型
            paper = Paper(
                id=f"arxiv:{result.entry_id.split('/')[-1]}",
                title=result.title,
                abstract=result.summary.replace("\n", " "),
                authors=[a.name for a in result.authors],
                url=result.pdf_url,
                published_date=result.published,
                source="arxiv",
                is_oa=True,
                doi=result.doi if result.doi else None,
                full_text_content=None,
                fetched_date=now,
            )
            papers_found.append(paper)

        logger.success(f"✅ Arxiv Scout 找到了 {len(papers_found)} 篇论文。")
        return papers_found
