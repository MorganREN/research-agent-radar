from src.research_agent.agents.analysis.parser import PDFParser
from src.research_agent.storage.models import Paper, engine

from sqlmodel import Session, select
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from loguru import logger
import datetime as dt
from typing import Optional
from src.research_agent.llm.kimi import (
    KIMI_BASE_URL,
    build_kimi_extra_body,
    extract_message_content,
)

load_dotenv()
CONFIG_MODEL = "kimi-k2.5"
KIMI_EXTRA_BODY = build_kimi_extra_body(CONFIG_MODEL, KIMI_BASE_URL)

PARSE_PROMPT = """\
You are a helpful assistant that extracts key information from academic papers.
Given the content of a paper, extract the following information and return ONLY a valid JSON object:

{
  "title": "The title of the paper",
  "abstract": "The abstract of the paper",
  "authors": ["Author 1", "Author 2"],
  "published_date": "YYYY-MM-DD or empty string if not found"
}

Rules:
- Return ONLY the JSON object, no other text.
- If any field is not found, return an empty string "" or empty list [].
- For authors, return a list of strings with full names.
- For published_date, use ISO format YYYY-MM-DD if available.
"""


class PDFUploadParser:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("KIMI_API_KEY"),
            base_url=KIMI_BASE_URL,
        )
        self.parser = PDFParser()

    def _upsert_paper(self, paper: Paper):
        """将论文信息插入或更新到数据库（同名 PDF 重复上传时不会报错）"""
        try:
            with Session(engine) as session:
                existing = session.get(Paper, paper.id)
                if existing:
                    # 更新已有记录的字段
                    existing.title = paper.title
                    existing.abstract = paper.abstract
                    existing.authors = paper.authors
                    existing.url = paper.url
                    existing.published_date = paper.published_date
                    existing.fetched_date = paper.fetched_date
                    session.add(existing)
                    logger.info(f"🔄 已更新数据库中的论文: {paper.title}")
                else:
                    session.add(paper)
                    logger.info(f"✅ 论文信息已存储到数据库: {paper.title}")
                session.commit()
                # 将 paper 从 session 脱离，避免 session 关闭后访问属性报 detached 错误
                session.expunge(existing if existing else paper)
        except Exception as e:
            logger.error(f"数据库存储错误: {e}")
            raise

    def _parse_date(self, date_str: str) -> dt.datetime:
        """尝试解析日期字符串，失败则返回今天"""
        if not date_str:
            return dt.datetime.today()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
            try:
                return dt.datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return dt.datetime.today()

    def parse_info(self, pdf_path: str) -> Optional[Paper]:
        """
        从 PDF 中提取关键信息（标题、摘要、作者等）并存入数据库。
        
        Returns:
            Paper 对象（成功时），None（失败时）
        """
        # Step 1: 本地解析 PDF → Markdown
        logger.info(f"📄 开始解析 PDF: {pdf_path}")
        try:
            full_text = self.parser.parse_to_markdown(pdf_path)
        except Exception as e:
            logger.error(f"PDF 文件解析失败: {e}")
            return None

        if not full_text or len(full_text.strip()) < 100:
            logger.error(f"PDF 解析结果为空或内容过短 ({len(full_text) if full_text else 0} 字符)，"
                         f"可能是扫描版 PDF 或文件损坏: {pdf_path}")
            return None

        logger.info(f"📄 PDF 解析完成，全文长度: {len(full_text)} 字符")

        # Step 2: 调用 LLM 提取结构化信息
        try:
            response = self.client.chat.completions.create(
                model=CONFIG_MODEL,
                messages=[
                    {"role": "system", "content": PARSE_PROMPT},
                    {"role": "user", "content": f"论文全文内容:\n{full_text[:50000]}"},
                ],
                response_format={"type": "json_object"},
                extra_body=KIMI_EXTRA_BODY,
            )
            raw_content = extract_message_content(response.choices[0].message)
            if not raw_content:
                finish_reason = getattr(response.choices[0], "finish_reason", "unknown")
                logger.error(f"LLM 返回空 content，finish_reason={finish_reason}")
                return None
            logger.debug(f"📑 LLM 原始响应: {raw_content[:500]}")
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return None

        # Step 3: 解析 JSON 响应
        try:
            basic_info = json.loads(raw_content)
        except json.JSONDecodeError:
            # Fallback: 尝试从响应中提取 JSON 部分
            logger.warning("JSON 直接解析失败，尝试提取 JSON 片段...")
            try:
                json_start = raw_content.find("{")
                json_end = raw_content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    basic_info = json.loads(raw_content[json_start:json_end])
                else:
                    logger.error(f"无法从 LLM 响应中找到 JSON: {raw_content[:300]}")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析最终失败: {e}\n响应内容: {raw_content[:300]}")
                return None

        # Step 4: 验证必要字段
        title = basic_info.get("title", "").strip()
        if not title:
            logger.error(f"LLM 未能提取到论文标题，响应: {basic_info}")
            return None

        # Step 5: 构建 Paper 对象
        authors = basic_info.get("authors", [])
        if authors is None:
            authors = []
        elif isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        elif not isinstance(authors, list):
            logger.warning(f"authors 字段类型异常 ({type(authors)}), 转为空列表")
            authors = []

        paper = Paper(
            id=f"uploaded:{os.path.basename(pdf_path)}",
            title=title,
            abstract=basic_info.get("abstract", ""),
            authors=authors,
            url=f"https://google.com/search?q={title.replace(' ', '+')}",
            published_date=self._parse_date(basic_info.get("published_date", "")),
            source="uploaded_pdf",
            is_relevant=True,
            relevance_score=10,
            triage_status="completed",
            download_status="downloaded",
            fetched_date=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
        )

        # Step 6: 存入数据库
        try:
            self._upsert_paper(paper)
        except Exception:
            return None

        logger.info(f"✅ 成功解析论文: {paper.title}")
        return paper


if __name__ == "__main__":
    parser_upload = PDFUploadParser()
    sample_pdf = "data/1-s2.0-S0926580524002826-main.pdf"
    result = parser_upload.parse_info(sample_pdf)
    if result:
        print(f"✅ 解析成功: {result.title}")
    else:
        print("❌ 解析失败")
