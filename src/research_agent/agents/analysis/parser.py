# src/agents/analysis/parser.py
import pymupdf4llm
import os

class PDFParser:
    def parse_to_markdown(self, pdf_path: str) -> str:
        """
        将 PDF 转换为 Markdown 文本，保留标题层级和表格。
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件未找到: {pdf_path}")
            
        print(f"📄 正在解析 PDF 结构: {pdf_path}...")
        try:
            # 这是一个非常强大的函数，它会自动处理双栏布局
            md_text = pymupdf4llm.to_markdown(pdf_path)
            
            # 简单的清洗，防止 token 溢出（保留前 50k 字符通常足够包含核心内容，可视情况调整）
            # 或者保留全文，交给长窗口模型处理
            return md_text
        except Exception as e:
            print(f"❌ 解析失败: {e}")
            return ""
        

if __name__ == "__main__":
    parser = PDFParser()
    sample_pdf = "data/papers/arxiv_2601.22149v1.pdf"  # 替换为实际的 PDF 文件路径
    markdown_content = parser.parse_to_markdown(sample_pdf)
    print(markdown_content[:1000])  # 打印前 1000 字符预览