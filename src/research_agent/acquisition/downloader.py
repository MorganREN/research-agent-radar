import os
import requests
# from src.research_agents.acquisition.browser_engine import BrowserEngine

class DownloadManager:
    def __init__(self, storage_dir="data/papers"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        # self.browser_engine = BrowserEngine()

    def _is_valid_pdf(self, file_path: str) -> bool:
        """简单的 PDF 文件头校验"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                return header == b"%PDF"
        except:
            return False

    def download_arxiv_direct(self, url: str, save_path: str) -> bool:
        """策略 A: arXiv 直接下载 (快速)"""
        try:
            # 将 /abs/ 替换为 /pdf/
            pdf_url = url.replace("/abs/", "/pdf/") + ".pdf"
            response = requests.get(pdf_url, timeout=30)
            if response.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Arxiv 下载错误: {e}")
            return False

    async def process_download(self, paper_id: str, url: str, source: str) -> str:
        """
        主入口。返回: 'downloaded', 'failed', 'login_required'
        """
        filename = f"{paper_id.replace(':', '_')}.pdf"
        save_path = os.path.join(self.storage_dir, filename)
        
        if os.path.exists(save_path):
            print(f"📦 文件已存在: {filename}")
            return "downloaded"

        success = False
        
        # === 路由逻辑 ===
        if "arxiv" in source.lower():
            print("🚀 使用 HTTP 直接下载策略 (Arxiv)")
            success = self.download_arxiv_direct(url, save_path)
        else:
            print("🕵️ 使用 浏览器 仿真下载策略 (Auth/External)")
            # 只有非 arXiv 才启动浏览器，节省资源
            # success = await self.browser_engine.download_pdf(url, save_path)

        # === 结果校验 ===
        if success and self._is_valid_pdf(save_path):
            return "downloaded"
        else:
            # 下载了但不是PDF（可能是登录页或验证码页）
            if os.path.exists(save_path): os.remove(save_path) 
            return "failed"
            

async def main():
    downloarder = DownloadManager()
    with Session(engine) as session:
        statement = select(Paper).where(Paper.is_relevant == True).\
            where(Paper.download_status == "pending")
        papers_to_download = session.exec(statement).all()
        logger.info(f"找到 {len(papers_to_download)} 篇待下载论文。")

        for paper in papers_to_download:
            logger.info(f"开始下载论文: {paper.id} ...")

            status = await downloarder.process_download(
                paper_id=paper.id,
                url=paper.url,
                source=paper.source
            )

            paper.download_status = status
            session.add(paper)
            session.commit()
    
            logger.info(f"论文 {paper.id} 下载状态: {status}")

if __name__ == "__main__":
    from src.research_agent.storage.models import Paper, engine
    from sqlmodel import Session, select
    from loguru import logger
    import asyncio
    
    asyncio.run(main())
    