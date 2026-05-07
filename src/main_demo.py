from sqlmodel import Session, select
from src.research_agent.storage.models import Paper, create_db_and_tables, engine
from src.research_agent.agents.scout.arxiv_scout import ArxivScout
from src.research_agent.agents.scout.elsevier_scout import ElsevierScout
from src.research_agent.agents.filter.triage_agent import RelevanceFilter, MIN_STORE_SCORE
from src.research_agent.acquisition.downloader import DownloadManager
from src.research_agent.agents.analysis.reviewer import PaperReviewer, ANALYSIS_MIN_SCORE
from loguru import logger
import asyncio

def run_ingestion_pipeline():
    # 1. 初始化数据库
    create_db_and_tables()
    
    # 2. 配置你的研究兴趣 (这是高度定制化的部分)
    # 结合了 AI 和 土木/隧道工程 [cite: 244]
    my_interests = """
    1. 人工智能在土木工程中的应用。
    2. 隧道工程的变形预测、结构健康监测
    3. 数字孪生技术
    4. 人工智能
    5. 大语言模型
    6. 音乐生成
    7. 视频生成模型和计算机视觉
    """
    
    # 3. 初始化 Agents
    # 3.1 搜索 arXiv 的土木工程(cs.CE) 和 人工智能(cs.AI) 板块
    arxiv_scout = ArxivScout(query="cat:cs.CE OR cat:cs.AI", days_back=7)
    # 3.2 搜索 Elsevier 的指定期刊
    elsevier_scout = ElsevierScout(
        max_results=30,
        year=2026
    )

    # 4. 初始化 Filter
    triage = RelevanceFilter(research_interests=my_interests)
    
    # 5. 运行 Scout (侦察)
    new_papers = []
    new_papers += arxiv_scout.fetch_papers()
    new_papers += elsevier_scout.fetch_papers()


    with Session(engine) as session:
        for paper in new_papers:
            # 5.1 去重检查 (检查数据库是否已存在)
            existing_paper = session.get(Paper, paper.id)
            if existing_paper:
                logger.info(f"⏭️  跳过已存在的论文: {paper.id}")
                continue
            
            # 5.2 运行 Filter (筛选)
            logger.info(f"🧠 正在分析论文相关性: {paper.title[:50]}...")
            result = triage.check_relevance(paper.title, paper.abstract)
            
            # 5.3 更新结果
            paper.is_relevant = result['is_relevant']
            paper.relevance_reason = result['reason']
            paper.relevance_score = result.get('relevance_score', 0)

            if (not paper.is_relevant) or (paper.relevance_score < MIN_STORE_SCORE):
                logger.info(
                    f"⏭️  跳过低相关论文: {paper.id} "
                    f"(is_relevant={paper.is_relevant}, score={paper.relevance_score})"
                )
                continue

            # 5.4 存入数据库
            session.add(paper)
            session.commit()

            icon = "✅" if paper.is_relevant else "❌"
            score_str = f" (评分: {paper.relevance_score}/10)" if paper.is_relevant else ""
            print(f"{icon} [{paper.id}] 判定结果: {paper.is_relevant}{score_str}")
            print(f"   理由: {paper.relevance_reason}\n")

async def run_analysis_phase():
    '''
    Docstring for run_analysis_phase
    '''
    reviewer = PaperReviewer()
    downloader = DownloadManager()

    with Session(engine) as session:
        # 1. 获取所有已相关且评分 >= ANALYSIS_MIN_SCORE 的论文
        papers = session.exec(
            select(Paper).where(
                Paper.is_relevant == True,
                Paper.relevance_score >= ANALYSIS_MIN_SCORE,
            )
        ).all()

        for paper in papers:
            if paper.analysis_report:
                logger.info(f"跳过已分析的论文: {paper.id}")
                continue
            logger.info(f"开始分析论文: {paper.id} ...")

            # 2. 确认 PDF 已下载
            save_path = f"data/papers/{paper.id}.pdf".replace(":", "_")
            if paper.download_status != "downloaded":
                status = await downloader.process_download(
                    paper_id=paper.id,
                    url=paper.url,
                    source=paper.source
                )
                if status != "downloaded":
                    logger.error(f"论文 {paper.id} 下载失败，跳过分析。")
                    continue
                paper.download_status = status
                session.add(paper)
                session.commit()

            # 3. 运行分析
            if paper.download_status == "downloaded":
                if paper.source == "arxiv":
                    report = reviewer.analyze_paper(paper, pdf_path=save_path)
                else:
                    report = reviewer.analyze_paper(paper, full_content=paper.full_text_content)
                paper.analysis_report = report
                session.add(paper)
                session.commit()
                logger.success(f"论文 {paper.id} 分析完成。")


if __name__ == "__main__":
    run_ingestion_pipeline()
    
    asyncio.run(run_analysis_phase())