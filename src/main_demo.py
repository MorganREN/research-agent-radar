from sqlmodel import Session, select
from src.research_agent.storage.models import Paper, create_db_and_tables, engine
from src.research_agent.agents.scourt.arxiv_scout import ArxivScout
from src.research_agent.agents.filter.triage_agent import RelevanceFilter
from src.research_agent.acquisition.downloader import DownloadManager

def run_ingestion_pipeline():
    # 1. 初始化数据库
    create_db_and_tables()
    
    # 2. 配置你的研究兴趣 (这是高度定制化的部分)
    # 结合了 AI 和 土木/隧道工程 [cite: 244]
    my_interests = """
    1. 人工智能在土木工程中的应用，特别是深度学习。
    2. 隧道工程的变形预测、结构健康监测。
    3. 数字孪生技术在地下基础设施中的应用。
    """
    
    # 3. 初始化 Agents
    # 搜索 arXiv 的土木工程(cs.CE) 和 人工智能(cs.AI) 板块
    scout = ArxivScout(query="cat:cs.CE OR cat:cs.AI", max_results=10)
    triage = RelevanceFilter(research_interests=my_interests)
    
    # 4. 运行 Scout (侦察)
    new_papers = scout.fetch_papers()
    
    with Session(engine) as session:
        for paper in new_papers:
            # 4.1 去重检查 (检查数据库是否已存在)
            existing_paper = session.get(Paper, paper.id)
            if existing_paper:
                print(f"⏭️  跳过已存在的论文: {paper.id}")
                continue
            
            # 4.2 运行 Filter (筛选)
            print(f"🧠 正在分析论文相关性: {paper.title[:50]}...")
            result = triage.check_relevance(paper.title, paper.abstract)
            
            # 4.3 更新结果
            paper.is_relevant = result['is_relevant']
            paper.relevance_reason = result['reason']
            
            # 4.4 存入数据库
            session.add(paper)
            session.commit()
            
            icon = "✅" if paper.is_relevant else "❌"
            print(f"{icon} [{paper.id}] 判定结果: {paper.is_relevant}")
            print(f"   理由: {paper.relevance_reason}\n")

if __name__ == "__main__":
    run_ingestion_pipeline()