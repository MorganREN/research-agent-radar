from src.research_agent.agents.analysis.parser import PDFParser
from src.research_agent.storage.models import Paper, engine

from sqlmodel import Session
from openai import OpenAI
import os
from dotenv import load_dotenv
from loguru import logger
import yaml
import datetime as dt

load_dotenv() # 加载 .env 中的 API KEY

class PDFUploadParser:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.parser = PDFParser() # 引用上面的解析器

    def refresh_database(self, paper: Paper):
        """将解析后的论文信息存储到数据库中"""
        try:
            with Session(engine) as session:
                session.add(paper)
                session.commit()
                session.refresh(paper)
                logger.info(f"✅ 论文信息已存储到数据库: {paper.title}")
        except Exception as e:
            logger.error(f"数据库存储错误: {e}")

    def parse_info(self, pdf_path: str) -> dict:
        """从 PDF 中提取关键信息（如标题、摘要等）"""
        parse_prompt = '''
    You are a helpful assistant that extracts key information from academic papers. Given the content of a paper, extract the following information in JSON format:
1. title: The title of the paper
2. abstract: The abstract of the paper
3. authors: A list of authors
4. published_date: The publication date (if available)

The output should be a JSON object with the above fields. If any field is not found, return an empty string or empty list for that field.
    '''
        full_text = self.parser.parse_to_markdown(pdf_path)
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": parse_prompt},
                    {"role": "user", "content": f"论文全文内容:\n{full_text[:10000]}"} # 截取前1w字符防溢出
                ]
            )
            print(f"📑 提取到的论文信息: {response.choices[0].message.content}")
            raw_reponse = response.choices[0].message.content
            # the original response may contain some explanation, we need to extract the JSON part
            try:
                json_start = raw_reponse.find("{")
                json_end = raw_reponse.rfind("}") + 1
                json_str = raw_reponse[json_start:json_end]
                basic_info = yaml.safe_load(json_str)
            except Exception as e:
                logger.warning(f"⚠️ 无法解析 JSON，使用原始响应: {e}")
                basic_info = yaml.safe_load(raw_reponse)  # 直接尝试解析整个响应

            paper = Paper(
                id=f"uploaded:{os.path.basename(pdf_path)}",
                title=basic_info.get("title", ""),
                abstract=basic_info.get("abstract", ""),
                authors=basic_info.get("authors", []),
                url=f"https://google.com/search?q={basic_info.get('title', '').replace(' ', '+')}",
                published_date=dt.datetime.today(),
                source="uploaded_pdf",
                is_relevant=True,  # 默认上传的论文都相关
                relevance_score=10,  # 用户主动上传的论文，相关度满分
                download_status="downloaded",
                fetched_date=dt.datetime.utcnow(),
            )

            logger.info(f"✅ 成功解析并存储论文: {paper.title}")
            self.refresh_database(paper)
            return paper
        except Exception as e:
            logger.error(f"LLM 信息提取出错: {e}")
            return {}



if __name__ == "__main__":
    parser_upload = PDFUploadParser()
    sample_pdf = "data/papers/buildings-13-02725-v4.pdf"  # 替换为实际的 PDF 文件路径
    print(parser_upload.parse_info(sample_pdf))