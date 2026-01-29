from src.research_agent.storage.models import Paper
import requests
import json
import datetime as dt
import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()  # 从 .env 文件加载环境变量

class ElsevierScout:
    def __init__(self, journals: list[str], max_results: int = 10, year: int = 2024):
        """
        journals: 目标期刊名称列表 (如 ["Computer Networks", "Ad Hoc Networks"])
        max_results: 每次搜索的最大结果数
        """
        self.journals = journals
        self.max_results = max_results
        self.year = year
        self.search_base_url = "https://api.elsevier.com/content/search/sciencedirect"
        self.api_key = os.getenv("ELSEVIER_API_KEY")
        self.headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json"
        }
        self.doi_list = []

    def _fetch_abstract_and_fulltext(self, doi: str) -> tuple[str | None, str | None]:
        """
        根据 DOI 获取论文的摘要和全文内容（如果可用）
        """
        base_url = f"https://api.elsevier.com/content/article/doi/{doi}"
        # --- A. 获取 Abstract (JSON 格式) ---
        try:
            params = {"view": "FULL"}
            json_headers = self.headers.copy()
            json_headers["Accept"] = "application/json"
            r_meta = requests.get(base_url, headers=json_headers, params=params)
            if r_meta.status_code == 200:
                data = r_meta.json()
                core_data = data.get('full-text-retrieval-response', {}).get('coredata', {})
                abstract = core_data.get('dc:description', "Abstract not found in metadata")
                if abstract:
                    abstract = abstract.strip()
                else:
                    logger.warning(f"⚠️ No abstract found for DOI: {doi}, status code: {r_meta.status_code}")
                    abstract = None
        except Exception as e:
            logger.warning(f"⚠️ Exception while fetching abstract for DOI {doi}: {e}")
            abstract = None
        full_text_content = ""
        # --- B. 获取 Full Text (XML 格式) ---
        try:
            xml_headers = self.headers.copy()
            xml_headers["Accept"] = "application/xml"
            r_fulltext = requests.get(base_url, headers=xml_headers, params=params)
            if r_fulltext.status_code == 200:
                full_text_content = r_fulltext.text  # 目前是直接存库，后续可考虑解析升级
            else:
                logger.warning(f"⚠️ No full text found for DOI: {doi}, status code: {r_fulltext.status_code}")
                full_text_content = None
        except Exception as e:
            logger.warning(f"⚠️ Exception while fetching full text for DOI {doi}: {e}")
            full_text_content = None

        return abstract, full_text_content

    def _fetch_papers_from_journal(self, journal_name: str) -> list[Paper]:
        query = {
            "query": f"SRCTITLE({journal_name}) AND PUBYEAR IS {self.year}",
            "count": self.max_results,
            "sort": "coverDate"
        }
        access_paper_count = 0
        non_access_paper_count = 0

        try:
            response = requests.get(self.search_base_url, headers=self.headers, params=query)
            response.raise_for_status()
            data = response.json()
        
            papers = []
            results = data.get('search-results', {}).get('entry', [])
            for item in results:
                doi = item.get('prism:doi')
                abstract, full_text_content = self._fetch_abstract_and_fulltext(doi)
                date = dt.datetime.strptime(item.get('prism:coverDate'), "%Y-%m-%d")
                logger.warning(f"Date: {date}, DATE TYPE: {type(date)}")
                if abstract: 
                    access_paper_count += 1
                else:
                    non_access_paper_count += 1
                paper = Paper(
                    id=f"elsevier:{item.get('dc:identifier').split(':')[-1]}",
                    title=item.get('dc:title'),
                    abstract=abstract,
                    authors=item.get('dc:creator'),
                    url=item.get('link', [{}])[0].get('@href'),
                    published_date=date,
                    source=f"elsevier:{journal_name}",
                    is_oa=None,    # Elsevier 论文的开放获取状态需要额外判断
                    doi=item.get('prism:doi'),
                    full_text_content=full_text_content
                )
                papers.append(paper)

            logger.success(f"✅ Elsevier Scout: {journal_name}，找到 {len(papers)} 篇论文 | 开放获取论文数: {access_paper_count}, 非开放获取论文数: {non_access_paper_count}")
            return papers
        except Exception as e:
            logger.error(f"Elsevier 搜索失败 ({journal_name}): {e}")
            return []

    def fetch_papers(self) -> set[Paper]:
        for journal in self.journals:
            logger.info(f"🕵️ Scout 正在 Elsevier 搜索期刊: {journal} ...")
            papers = self._fetch_papers_from_journal(journal)
            self.doi_list += papers
        return list(self.doi_list)
    
    

if __name__ == "__main__":
    journals = [
        'Tunnelling and Underground Space Technology',
        'Automation in Construction'
    ]
    scout = ElsevierScout(journals=journals, max_results=5, year=2024)
    papers = scout.fetch_papers()
    for paper in papers:
        print(f"{paper.title} ({paper.published_date})")
        if paper.abstract:
            print(f"Abstract: {paper.abstract[:200]}...")
        else:
            print("Abstract: Not available")