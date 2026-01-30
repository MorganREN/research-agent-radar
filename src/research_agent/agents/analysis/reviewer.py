# src/agents/analysis/reviewer.py
from openai import OpenAI
import os
from loguru import logger
from src.research_agent.storage.models import Paper
from src.research_agent.agents.analysis.parser import PDFParser
from dotenv import load_dotenv

load_dotenv() # 加载 .env 中的 API KEY

class PaperReviewer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.parser = PDFParser() # 引用上面的解析器

    def analyze_paper(self, paper: Paper, pdf_path: str=None, xml_content: str=None) -> str:
        # 1. 解析 PDF 或 XML
        if xml_content and not pdf_path:  # 使用 XML 内容（如来自 Elsevier）
            full_text = xml_content
        elif pdf_path and not xml_content:  # 使用 PDF 文件
            full_text = self.parser.parse_to_markdown(pdf_path)
        else:
            logger.error("必须提供 PDF 路径或 XML 内容进行分析。")
            return "解析失败，无法生成报告。"
        if not full_text:
            return "解析失败，无法生成报告。"

        print(f"🧠 正在深度阅读论文: {paper.title}...")

        # 2. 博士级分析 Prompt
        # 这里的 Prompt 设计非常关键，必须强制结构化输出
        system_prompt = """
        你是一位"人工智能+土木工程"交叉领域的资深审稿人。
        你的任务是阅读一篇学术论文，并为一位正在攻读该领域PhD的学生撰写一份深度分析报告。
        
        请使用 Markdown 格式，严格按照以下结构输出报告：
        
        # 1. 核心贡献 (Core Contribution)
        - 用一句话概括本文解决的痛点。
        - 本文提出的核心方法/模型是什么？（如使用了什么具体的GNN变体、Attention机制等）
        
        # 2. 技术拆解 (Technical Implementation)
        - **数据来源**: 数据集是什么？是否开源？
        - **输入输出**: 模型的输入特征是什么？输出目标是什么？
        - **基准对比**: 相比 SOTA 模型提升了多少？
        
        # 3. 创新点与缺陷 (Strengths & Weaknesses)
        - ✅ **创新点**: (列出2-3点，如：首次将XX用于隧道沉降预测)
        - ⚠️ **潜在缺陷**: (列出2-3点，如：实验数据量不足、泛化能力存疑、未考虑工程地质复杂性)
        
        # 4. 对PhD研究的启示 (Implications)
        - 这篇论文的方法论是否可以迁移到"隧道数字孪生"或"大型基础设施运维"中？
        - 如果要复现，最大的难点可能在哪里？
        
        ---
        请保持语气客观、批判性，不要单纯复述摘要。
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # 建议使用 GPT-4o 以获得最佳推理能力
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"论文标题: {paper.title}\n\n论文全文内容:\n{full_text[:60000]}"} # 截取前6w字符防溢出
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