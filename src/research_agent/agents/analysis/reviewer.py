# src/agents/analysis/reviewer.py
from openai import OpenAI
import os
from loguru import logger
from src.research_agent.storage.models import Paper
from src.research_agent.agents.analysis.parser import PDFParser
from dotenv import load_dotenv
import yaml
from pathlib import Path
from typing import List

load_dotenv() # 加载 .env 中的 API KEY

# 单次直接分析的最大字符数（约 15k tokens，留出 prompt 和回复的空间）
MAX_CHARS_DIRECT = 60_000
# 分块大小（约 5k tokens per chunk）
CHUNK_SIZE = 20_000

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

Provide your analysis in well-structured Markdown.
"""

CHUNK_EXTRACTION_PROMPT = """
You are reading a segment of an academic paper. Extract all key information from this segment that would be useful for a comprehensive review. Focus on:
- Main claims, contributions, and findings
- Methodology and technical details
- Results and evaluation metrics
- Limitations mentioned
- Any conclusions drawn

Be concise but thorough. Preserve important numerical results and technical terms.
"""

SYNTHESIS_PROMPT = """
You are an expert academic reviewer. Based on the extracted key points from all sections of a paper (provided below), write a comprehensive review covering:

1. One-line TL;DR
2. Summary (3-5 bullet points)
3. Recommendation (Read in depth / Skim / Not relevant)
4. Technical evaluation (novelty, correctness, methodology)
5. Strengths (top 3)
6. Weaknesses (top 3)
7. Potential applications
8. Follow-up research directions

Provide your analysis in well-structured Markdown.
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
                        return prompt
                logger.warning("⚠️ No 'reviewer_prompt template' found in analysis_prompt.yaml, using DEFAULT_PROMPT")
            else:
                logger.warning(f"⚠️ Config file not found at {config_path}, using DEFAULT_PROMPT")
        except Exception as e:
            logger.warning(f"⚠️ Error loading config: {e}, using DEFAULT_PROMPT")
        return DEFAULT_PROMPT

    def _split_into_chunks(self, text: str) -> List[str]:
        """将文本按段落边界切分为大小合适的块，避免在句子中间截断。"""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > CHUNK_SIZE and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len + 2  # +2 for "\n\n"

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _extract_chunk_keypoints(self, chunk: str, chunk_index: int, total_chunks: int) -> str:
        """对单个文本块调用 LLM，提取关键信息。"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # 用更快的模型处理每个块
                messages=[
                    {"role": "system", "content": CHUNK_EXTRACTION_PROMPT},
                    {"role": "user", "content": f"[Paper segment {chunk_index + 1}/{total_chunks}]\n\n{chunk}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"提取第 {chunk_index + 1} 块关键信息失败: {e}")
            return f"[Segment {chunk_index + 1} extraction failed: {e}]"

    @staticmethod
    def _build_paper_metadata(paper: Paper) -> str:
        """从 Paper 对象中构建元数据文本块。"""
        authors_str = ", ".join(paper.authors) if paper.authors else "N/A"
        date_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"
        lines = [
            f"Title: {paper.title}",
            f"Authors: {authors_str}",
            f"Published: {date_str}",
            f"Source: {paper.source}",
        ]
        if paper.doi:
            lines.append(f"DOI: {paper.doi}")
        if paper.url:
            lines.append(f"URL: {paper.url}")
        lines.append(f"\nAbstract:\n{paper.abstract}")
        return "\n".join(lines)

    def _synthesize_from_keypoints(self, paper: Paper, keypoints: List[str], system_prompt: str) -> str:
        """将各块的关键信息汇总，调用 LLM 生成最终分析报告。"""
        combined = "\n\n---\n\n".join(
            f"**Extracted points from segment {i + 1}:**\n{kp}"
            for i, kp in enumerate(keypoints)
        )
        metadata = self._build_paper_metadata(paper)

        # 汇总步骤始终需要告知 LLM 输入是提取的关键点，而非完整全文。
        # 用强制前缀覆盖自定义 prompt 中可能存在的 "ask for more info" 指令。
        override_prefix = (
            "IMPORTANT: You already have the paper's full bibliographic metadata AND "
            "key points extracted from every section of the paper. You have ALL the "
            "information needed. Do NOT ask for additional information — proceed directly "
            "with the analysis.\n\n"
        )
        if system_prompt != DEFAULT_PROMPT:
            synthesis_system = override_prefix + system_prompt
        else:
            synthesis_system = override_prefix + SYNTHESIS_PROMPT

        user_content = (
            f"## Paper Metadata\n{metadata}\n\n"
            f"## Extracted Key Points from Full Text\n\n{combined}"
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {"role": "system", "content": synthesis_system},
                    {"role": "user", "content": user_content}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM 汇总分析出错: {e}"

    def analyze_paper(self, paper: Paper, pdf_path: str=None, full_content: str=None) -> str:
        # 1. 解析 PDF 或 XML
        if full_content and not pdf_path:  # 使用 XML 内容（如来自 Elsevier）
            full_text = full_content
        elif pdf_path and not full_content:  # 使用 PDF 文件
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

        # 2. 根据文本长度选择直接分析或分块 Map-Reduce
        metadata = self._build_paper_metadata(paper)

        if len(full_text) <= MAX_CHARS_DIRECT:
            logger.info(f"论文长度 {len(full_text)} 字符，直接分析。")
            try:
                response = self.client.chat.completions.create(
                    model="gpt-5.1",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"## Paper Metadata\n{metadata}\n\n## Full Text\n{full_text}"}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"LLM 分析出错: {e}"
        else:
            # Map-Reduce：分块提取关键信息，再汇总生成报告
            chunks = self._split_into_chunks(full_text)
            logger.info(f"论文长度 {len(full_text)} 字符，超出限制，分为 {len(chunks)} 块进行 Map-Reduce 分析。")
            print(f"论文内容较长，将分 {len(chunks)} 段提取关键信息后汇总分析...")

            keypoints = []
            for i, chunk in enumerate(chunks):
                print(f"  正在分析第 {i + 1}/{len(chunks)} 段...")
                kp = self._extract_chunk_keypoints(chunk, i, len(chunks))
                keypoints.append(kp)

            print("  正在汇总所有段落信息，生成最终报告...")
            return self._synthesize_from_keypoints(paper, keypoints, system_prompt)
        

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