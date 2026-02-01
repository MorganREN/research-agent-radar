# src/agents/analysis/reviewer.py
from openai import OpenAI
import os
from loguru import logger
from src.research_agent.storage.models import Paper
from src.research_agent.agents.analysis.parser import PDFParser
from dotenv import load_dotenv
import yaml
from pathlib import Path

load_dotenv() # 加载 .env 中的 API KEY

DEFAULT_PROMPT = """
You are an expert academic reviewer. Analyze the following paper and provide:

1. One-line TL;DR
2. Summary (3-5 bullet points)
3. Recommendation (Read in depth / Skim / Not relevant)
4. Technical evaluation (novelty, correctness, methodology)
5. Strengths (top 3)
6. Weaknesses (top 3)
7. Potential applications
8. Follow-up research directions

Provide your analysis in well-structured Markdown format.
"""

class PaperReviewer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.parser = PDFParser() # 引用上面的解析器

    def _load_reviewer_prompt(self) -> str:
        """Load reviewer prompt from analysis_prompt.yaml"""
        config_path = Path(__file__).parent.parent.parent / "config" / "analysis_prompt.yaml"
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config and "template" in config:
                        prompt = config["template"]
                        logger.info("✅ Loaded reviewer prompt from analysis_prompt.yaml")
                        return prompt
                logger.warning("⚠️ No 'reviewer_prompt template' found in analysis_prompt.yaml, using DEFAULT_PROMPT")
            else:
                logger.warning(f"⚠️ Config file not found at {config_path}, using DEFAULT_PROMPT")
        except Exception as e:
            logger.warning(f"⚠️ Error loading config: {e}, using DEFAULT_PROMPT")
        return DEFAULT_PROMPT

    def analyze_paper(self, paper: Paper, pdf_path: str=None, xml_content: str=None) -> str:
        # 1. 解析 PDF 或 XML
        if xml_content and not pdf_path:  # 使用 XML 内容（如来自 Elsevier）
            full_text = xml_content
        elif pdf_path and not xml_content:  # 使用 PDF 文件
            full_text = self.parser.parse_to_markdown(pdf_path)
        else:
            logger.error("必须提供 PDF 路径或 XML 内容进行分析。")
            return "☹️ 解析失败，无法生成报告。"
        if not full_text:
            return "☹️ 解析失败，无法生成报告。"

        print(f"🧠 正在深度阅读论文: {paper.title}...")

        # 2. 博士级分析 Prompt
        # 这里的 Prompt 设计非常关键，必须强制结构化输出
        system_prompt = self._load_reviewer_prompt()

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # 建议使用 GPT-4o 以获得最佳推理能力
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"论文标题: {paper.title}\n\n论文全文内容:\n{full_text}"} # 截取前6w字符防溢出
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM 分析出错: {e}"
        

if __name__ == "__main__":
    # 测试代码
    from src.research_agent.storage.models import Paper, engine
    from sqlmodel import Session, select
    reviewer = PaperReviewer()
    with Session(engine) as session:
        statement = select(Paper).where(Paper.is_relevant == True).\
            where(Paper.download_status == "downloaded").\
            where(Paper.source == "arxiv")
        papers = session.exec(statement).all()
        if not papers:
            print("❌ 没有找到待分析的论文。")
            exit(1)
        sample_paper = papers[0]  # 取第一个待分析的论文
    sample_pdf_path = f"data/papers/{sample_paper.id}.pdf".replace(":", "_")  # 假设 PDF 文件名与论文 ID 一致
    report = reviewer.analyze_paper(sample_paper, pdf_path=sample_pdf_path)
    print(report)