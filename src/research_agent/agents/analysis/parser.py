# src/agents/analysis/parser.py
import pymupdf4llm
import os
from loguru import logger


class PDFParser:
    def parse_to_markdown(self, pdf_path: str) -> str:
        """
        将 PDF 转换为 Markdown 文本，保留标题层级和表格。
        失败时抛出异常（而非静默返回空字符串），让调用方决定如何处理。
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件未找到: {pdf_path}")

        file_size = os.path.getsize(pdf_path)
        if file_size < 1024:  # < 1KB 的文件几乎不可能是有效 PDF
            raise ValueError(f"PDF 文件过小 ({file_size} bytes)，可能已损坏: {pdf_path}")

        logger.info(f"📄 正在解析 PDF 结构: {pdf_path} ({file_size / 1024:.1f} KB)")
        try:
            md_text = pymupdf4llm.to_markdown(pdf_path)
            if not md_text or len(md_text.strip()) < 50:
                raise ValueError(f"PDF 解析结果为空，可能是扫描版 PDF 或加密文件: {pdf_path}")
            logger.info(f"✅ PDF 解析完成: {len(md_text)} 字符")
            return md_text
        except Exception as e:
            logger.error(f"❌ PDF 解析失败: {e}")
            raise
        

if __name__ == "__main__":
    parser = PDFParser()
    sample_pdf = "data/papers/arxiv_2601.22149v1.pdf"  # 替换为实际的 PDF 文件路径
    markdown_content = parser.parse_to_markdown(sample_pdf)
    print(markdown_content[:1000])  # 打印前 1000 字符预览