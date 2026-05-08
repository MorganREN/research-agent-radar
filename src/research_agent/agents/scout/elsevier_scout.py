from src.research_agent.storage.models import Paper
import requests
import datetime as dt
import os
from dotenv import load_dotenv
from loguru import logger
from bs4 import BeautifulSoup

load_dotenv()  # 从 .env 文件加载环境变量

DEFAULT_JOURNALS = [
        # "Computer Networks",
        # "Ad Hoc Networks",
        # "Tunnelling and Underground Space Technology",
        "Automation in Construction"
    ]

def parse_elsevier_xml_to_markdown(xml_content):
    # 建议使用 'lxml-xml' 解析器来处理 XML
    soup = BeautifulSoup(xml_content, 'lxml-xml')
    markdown_lines = []

    # 1. 提取文章主标题
    # Elsevier 通常使用 <dc:title> 或 <ce:title> 作为主标题
    title_node = soup.find('dc:title') or soup.find('ce:title')
    if title_node:
        markdown_lines.append(f"# {title_node.get_text(strip=True)}\n")

    # 2. 提取摘要
    abstract_node = soup.find('ce:abstract')
    if abstract_node:
        markdown_lines.append("## Abstract\n")
        # 摘要内可能有多个段落
        for para in abstract_node.find_all('ce:para'):
            markdown_lines.append(f"{para.get_text(strip=True)}\n")

    # 3. 提取正文主体
    # Elsevier 正文通常包含在 <ce:sections> 中，由多个 <ce:section> 组成
    sections = soup.find_all('ce:section')
    for section in sections:
        # 提取章节标题
        sec_title = section.find('ce:section-title')
        if sec_title:
            markdown_lines.append(f"## {sec_title.get_text(strip=True)}\n")
        
        # 提取章节内的段落
        # 注意只获取当前 section 的直接段落，避免嵌套过深导致重复提取
        for para in section.find_all('ce:para', recursive=False):
            markdown_lines.append(f"{para.get_text(strip=True)}\n")
            
        # (可选) 处理子章节 <ce:section> 的递归或查找，这里简略展示主逻辑

    # 将列表合并为完整的 Markdown 字符串
    clean_markdown = "\n".join(markdown_lines)
    return clean_markdown

class ElsevierScout:
    def __init__(
        self,
        journals: list[str] | None = None,
        max_results: int = 10,
        year: int = 2024,
    ):
        """
        journals: 目标期刊名称列表 (如 ["Computer Networks", "Ad Hoc Networks"])
        max_results: 每次搜索的最大结果数
        """
        self.journals = journals or DEFAULT_JOURNALS
        self.max_results = max_results
        self.year = year
        self.search_base_url = "https://api.elsevier.com/content/search/sciencedirect"
        self.api_key = os.getenv("ELSEVIER_API_KEY") or os.getenv("ELSEVIER_API_KEY_BACKUP")
        self.headers = {
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json"
        }
        self.papers: list[Paper] = []

    def _fetch_abstract_and_fulltext(self, doi: str) -> tuple[str | None, str | None]:
        """
        根据 DOI 获取论文的摘要和全文内容（如果可用）
        """
        base_url = f"https://api.elsevier.com/content/article/doi/{doi}"
        params = {"view": "FULL"}
        abstract = None
        # --- A. 获取 Abstract (JSON 格式) ---
        try:
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
            else:
                logger.warning(f"⚠️ No metadata found for DOI: {doi}, status code: {r_meta.status_code}")
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
                full_text_content = parse_elsevier_xml_to_markdown(r_fulltext.text)  # 当前解析xml的方法由AI生成，后续可以根据实际情况调整
            else:
                logger.warning(f"⚠️ No full text found for DOI: {doi}, status code: {r_fulltext.status_code}")
                full_text_content = None
        except Exception as e:
            logger.warning(f"⚠️ Exception while fetching full text for DOI {doi}: {e}")
            full_text_content = None

        return abstract, full_text_content
    
    def _parse_authors(self, authors_data) -> list[str] | None:
        if not authors_data:
            return None
        authors = authors_data.get("author", [])
        if isinstance(authors, list):
            authors = [a['$'] for a in authors]
            return authors
        else:
            return [authors.get('$')]

    def _fetch_papers_from_journal(self, journal_name: str) -> list[Paper]:
        if not self.api_key:
            logger.error("Elsevier API key is missing. Set ELSEVIER_API_KEY in .env.")
            return []

        query = {
            "query": f"SRCTITLE({journal_name}) AND PUBYEAR IS {self.year}",
            "count": self.max_results,
            "sort": "coverDate"
        }
        access_paper_count = 0
        non_access_paper_count = 0
        papers = []
        try:
            response = requests.get(self.search_base_url, headers=self.headers, params=query)
            response.raise_for_status()
            data = response.json()
        
            results = data.get('search-results', {}).get('entry', [])
            for item in results:
                # logger.info(f"Fetched abstract for DOI {item.get('dc:title')}:")
                doi = item.get('prism:doi')
                if not doi:
                    continue
                abstract, full_text_content = self._fetch_abstract_and_fulltext(doi)
                cover_date = item.get('prism:coverDate')
                if not cover_date:
                    continue
                date = dt.datetime.strptime(cover_date, "%Y-%m-%d")
                if abstract: 
                    access_paper_count += 1
                else:
                    non_access_paper_count += 1
                    continue  # 跳过非开放获取论文
                authors = self._parse_authors(item.get('authors'))
                if not authors:
                    continue
                identifier = item.get('dc:identifier') or doi
                links = item.get('link') or []
                url = links[1].get('@href') if len(links) > 1 else item.get('prism:url')
                title = item.get('dc:title')
                if not title or not url:
                    continue
                paper = Paper(
                    id=f"elsevier:{identifier.split(':')[-1]}",
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    url=url,
                    published_date=date,
                    source=f"elsevier:{journal_name}",
                    is_oa=None,    # Elsevier 论文的开放获取状态需要额外判断
                    doi=item.get('prism:doi'),
                    full_text_content=full_text_content,
                    download_status="downloaded",
                    fetched_date=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                )
                papers.append(paper)

        except Exception as e:
            logger.error(f"Elsevier 搜索失败 ({journal_name}): {e}")
        if papers:
            logger.success(f"✅ Elsevier Scout: {journal_name}，找到 {len(papers)} 篇论文 | 开放获取论文数: {access_paper_count}, 非开放获取论文数: {non_access_paper_count}")
        return papers

    def fetch_papers(self) -> list[Paper]:
        self.papers = []
        for journal in self.journals:
            logger.info(f"🕵️ Scout 正在 Elsevier 搜索期刊: {journal} ...")
            papers = self._fetch_papers_from_journal(journal)
            self.papers += papers
        return list(self.papers)
    
    

if __name__ == "__main__":
    journals = [
        'Tunnelling and Underground Space Technology',
        'Automation in Construction'
    ]
    scout = ElsevierScout(max_results=5, year=2024)
    papers = scout.fetch_papers()
    for paper in papers:
        print(f"{paper.title} ({paper.published_date})")
        if paper.abstract:
            print(f"Abstract: {paper.abstract[:200]}...")
        else:
            print("Abstract: Not available")
