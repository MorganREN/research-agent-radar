# src/agents/analysis/reviewer.py
from openai import OpenAI
import os
from loguru import logger
from src.research_agent.storage.models import Paper
from src.research_agent.agents.analysis.parser import PDFParser
from src.research_agent.llm.kimi import (
    KIMI_BASE_URL,
    build_kimi_extra_body,
    extract_response_content,
)
from dotenv import load_dotenv
import yaml
from pathlib import Path
from typing import List

load_dotenv()

# ── 模型配置 ──────────────────────────────────────────────────────
# Kimi K2.5 支持 128K token 上下文窗口，绝大多数学术论文全文可一次性送入
CONFIG_MODEL = "kimi-k2.5"
KIMI_EXTRA_BODY = build_kimi_extra_body(CONFIG_MODEL, KIMI_BASE_URL)

# 直接分析上限：~200K 字符 ≈ ~50-60K tokens（为 prompt + 回复预留空间）
# Kimi K2.5 的 128K 窗口足以覆盖几乎所有学术论文
MAX_CHARS_DIRECT = 200_000
ANALYSIS_MIN_SCORE = 6

# 仅在极端超长文档时启用 Map-Reduce fallback
CHUNK_SIZE = 50_000  # 每块 ~12K tokens，减少分块次数

DEFAULT_PROMPT = """\
You are an expert academic reviewer with deep domain knowledge. \
You have access to the COMPLETE full text of the paper. \
Leverage the full content to provide a thorough and evidence-based analysis.

Analyze the paper and provide:

1. **TL;DR** — One sentence capturing the core contribution
2. **Summary** — 3-5 bullet points covering motivation, method, results
3. **Recommendation** — Read in depth / Skim / Not relevant (with justification)
4. **Technical Evaluation** — Assess novelty, correctness, methodology rigor, and reproducibility
5. **Strengths** — Top 3, with specific evidence from the paper
6. **Weaknesses** — Top 3, with specific evidence from the paper
7. **Key Results** — Highlight the most important quantitative results and comparisons
8. **Potential Applications** — Practical use cases and impact
9. **Follow-up Research Directions** — Open questions and future work

Provide your analysis in well-structured Markdown. \
Be specific — reference actual sections, figures, tables, and numbers from the paper.
"""

CHUNK_EXTRACTION_PROMPT = """\
You are reading a segment of an academic paper. \
Extract ALL key information from this segment that would be useful for a comprehensive review. Focus on:
- Main claims, contributions, and findings
- Methodology and technical details
- Results and evaluation metrics (preserve exact numbers)
- Limitations mentioned
- Any conclusions drawn

Be concise but thorough. Preserve important numerical results and technical terms.
"""

SYNTHESIS_PROMPT = """\
You are an expert academic reviewer. Based on the extracted key points from all sections of a paper, \
write a comprehensive review covering:

1. **TL;DR** — One sentence capturing the core contribution
2. **Summary** — 3-5 bullet points covering motivation, method, results
3. **Recommendation** — Read in depth / Skim / Not relevant (with justification)
4. **Technical Evaluation** — Assess novelty, correctness, methodology rigor, and reproducibility
5. **Strengths** — Top 3, with specific evidence
6. **Weaknesses** — Top 3, with specific evidence
7. **Key Results** — Highlight the most important quantitative results
8. **Potential Applications**
9. **Follow-up Research Directions**

IMPORTANT: You have ALL the information needed from the paper. \
Do NOT ask for additional information — proceed directly with the analysis.

Provide your analysis in well-structured Markdown.
"""


class PaperReviewer:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("KIMI_API_KEY"),
            base_url=KIMI_BASE_URL,
        )
        self.parser = PDFParser()

    def _load_reviewer_prompt(self) -> str:
        """Load reviewer prompt from analysis_prompt.yaml, fallback to DEFAULT_PROMPT."""
        config_path = Path(__file__).parent.parent.parent / "config" / "analysis_prompt.yaml"
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config and "template" in config:
                        return config["template"]
                logger.warning("⚠️ No 'template' found in analysis_prompt.yaml, using DEFAULT_PROMPT")
            else:
                logger.warning(f"⚠️ Config file not found at {config_path}, using DEFAULT_PROMPT")
        except Exception as e:
            logger.warning(f"⚠️ Error loading config: {e}, using DEFAULT_PROMPT")
        return DEFAULT_PROMPT

    def _extract_final_content(self, response) -> str:
        return extract_response_content(response)

    # ── 切块（仅 fallback 使用）────────────────────────────────────
    def _split_into_chunks(self, text: str) -> List[str]:
        """按段落边界切块，尽量保持大块以减少信息损失。"""
        paragraphs = text.split("\n\n")
        chunks, current_chunk, current_len = [], [], 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > CHUNK_SIZE and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        return chunks

    def _extract_chunk_keypoints(self, chunk: str, idx: int, total: int) -> str:
        """对单个文本块调用 LLM 提取关键信息。"""
        try:
            response = self.client.chat.completions.create(
                model=CONFIG_MODEL,
                messages=[
                    {"role": "system", "content": CHUNK_EXTRACTION_PROMPT},
                    {"role": "user", "content": f"[Paper segment {idx + 1}/{total}]\n\n{chunk}"},
                ],
                extra_body=KIMI_EXTRA_BODY,
            )
            return self._extract_final_content(response)
        except Exception as e:
            logger.warning(f"提取第 {idx + 1} 块关键信息失败: {e}")
            return f"[Segment {idx + 1} extraction failed: {e}]"

    # ── 元数据构建 ─────────────────────────────────────────────────
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

    # ── Map-Reduce 汇总（fallback）──────────────────────────────────
    def _synthesize_from_keypoints(self, paper: Paper, keypoints: List[str], system_prompt: str) -> str:
        """将各块关键信息汇总，生成最终分析报告。"""
        combined = "\n\n---\n\n".join(
            f"**Extracted points from segment {i + 1}:**\n{kp}"
            for i, kp in enumerate(keypoints)
        )
        metadata = self._build_paper_metadata(paper)

        # 使用 SYNTHESIS_PROMPT（自带 "不要追问" 指令），或自定义 prompt 加前缀
        if system_prompt != DEFAULT_PROMPT:
            synthesis_system = (
                "IMPORTANT: You already have the paper's full bibliographic metadata AND "
                "key points extracted from every section. Do NOT ask for additional information "
                "— proceed directly with the analysis.\n\n" + system_prompt
            )
        else:
            synthesis_system = SYNTHESIS_PROMPT

        try:
            response = self.client.chat.completions.create(
                model=CONFIG_MODEL,
                messages=[
                    {"role": "system", "content": synthesis_system},
                    {"role": "user", "content": (
                        f"## Paper Metadata\n{metadata}\n\n"
                        f"## Extracted Key Points from Full Text\n\n{combined}"
                    )},
                ],
                extra_body=KIMI_EXTRA_BODY,
            )
            return self._extract_final_content(response)
        except Exception as e:
            return f"LLM 汇总分析出错: {e}"

    # ── 主入口 ─────────────────────────────────────────────────────
    def analyze_paper(self, paper: Paper, pdf_path: str = None, full_content: str = None) -> str:
        """
        分析论文，优先使用 Kimi K2.5 的长上下文窗口直接全文分析。
        仅在极端超长文档时 fallback 到 Map-Reduce。
        """
        # 1. 获取全文
        if full_content and not pdf_path:
            full_text = full_content
        elif pdf_path and not full_content:
            full_text = self.parser.parse_to_markdown(pdf_path)
        else:
            logger.error("必须提供 PDF 路径或 XML 内容进行分析。")
            return "☹️ 解析失败，无法生成报告。"
        if not full_text:
            return "☹️ 解析失败，无法生成报告。"

        print(f"🧠 正在深度阅读论文: {paper.title}...")
        logger.info(f"论文全文长度: {len(full_text)} 字符")

        # 2. 博士级分析 Prompt
        # 这里的 Prompt 设计非常关键，必须强制结构化输出
        system_prompt = self._load_reviewer_prompt()

        # 2. 根据文本长度选择直接分析或分块 Map-Reduce
        metadata = self._build_paper_metadata(paper)

        # 2. 利用 Kimi K2.5 长上下文 — 绝大多数论文走直接分析
        if len(full_text) <= MAX_CHARS_DIRECT:
            logger.info(f"论文长度 {len(full_text)} 字符 ≤ {MAX_CHARS_DIRECT}，直接全文分析。")
            try:
                response = self.client.chat.completions.create(
                    model=CONFIG_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": (
                            f"## Paper Metadata\n{metadata}\n\n"
                            f"## Full Text\n{full_text}"
                        )},
                    ],
                    extra_body=KIMI_EXTRA_BODY,
                )
                return self._extract_final_content(response)
            except Exception as e:
                return f"LLM 分析出错: {e}"
        else:
            # 3. Fallback: Map-Reduce（仅在极端超长文档时触发）
            chunks = self._split_into_chunks(full_text)
            logger.info(
                f"论文长度 {len(full_text)} 字符 > {MAX_CHARS_DIRECT}，"
                f"分为 {len(chunks)} 块进行 Map-Reduce 分析。"
            )
            print(f"论文内容超长，将分 {len(chunks)} 段提取关键信息后汇总分析...")

            keypoints = []
            for i, chunk in enumerate(chunks):
                print(f"  正在分析第 {i + 1}/{len(chunks)} 段...")
                kp = self._extract_chunk_keypoints(chunk, i, len(chunks))
                keypoints.append(kp)

            print("  正在汇总所有段落信息，生成最终报告...")
            return self._synthesize_from_keypoints(paper, keypoints, system_prompt)


if __name__ == "__main__":
    from src.research_agent.storage.models import Paper, engine
    from sqlmodel import Session, select

    reviewer = PaperReviewer()
    with Session(engine) as session:
        statement = (
            select(Paper)
            .where(Paper.is_relevant == True)
            .where(Paper.relevance_score >= ANALYSIS_MIN_SCORE)
            .where(Paper.download_status == "downloaded")
            .where(Paper.source == "arxiv")
        )
        papers = session.exec(statement).all()
        if not papers:
            print("❌ 没有找到待分析的论文。")
            exit(1)
        sample_paper = papers[0]

    sample_pdf_path = f"data/papers/{sample_paper.id}.pdf".replace(":", "_")
    report = reviewer.analyze_paper(sample_paper, pdf_path=sample_pdf_path)
    print(report)