# src/dashboard/app.py
import sys
import os

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from sqlmodel import Session, select, desc
from src.research_agent.storage.models import Paper, engine
import os

# 页面配置
st.set_page_config(page_title="AI Research Agent", layout="wide", page_icon="🎓")

st.title("🎓 自动化学术情报局")
st.caption("AI + Civil Engineering Research Assistant")

# --- Sidebar: 侧边栏过滤器 ---
with st.sidebar:
    st.header("🔍 筛选控制")
    filter_source = st.multiselect("来源平台", ["arxiv", "sciencedirect", "asce"], default=["arxiv"])
    show_only_relevant = st.checkbox("只看高相关 (Relevant)", value=True)
    
    st.divider()
    st.info("数据每24小时自动更新。")

# --- Main Area: 数据加载 ---
def load_papers():
    with Session(engine) as session:
        statement = select(Paper).order_by(desc(Paper.published_date))
        if show_only_relevant:
            statement = statement.where(Paper.is_relevant == True)
        # 简单的来源过滤逻辑可以在这里加
        return session.exec(statement).all()

papers = load_papers()

if not papers:
    st.warning("暂无数据，请先运行 main_demo.py 抓取论文。")
else:
    # --- 布局：左侧列表，右侧详情 ---
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader(f"📄 最新论文 ({len(papers)})")
        selected_paper_id = st.radio(
            "选择论文查看详情:",
            options=[p.id for p in papers],
            format_func=lambda x: next((p.title for p in papers if p.id == x), x)
        )
        
        # 获取选中的论文对象
        current_paper = next(p for p in papers if p.id == selected_paper_id)

    with col2:
        if current_paper:
            # 标题区
            st.markdown(f"## {current_paper.title}")
            st.markdown(f"**作者**: {', '.join(current_paper.authors)} | **日期**: {current_paper.published_date.date()}")
            
            # 链接按钮
            if current_paper.url:
                st.link_button("🔗 原文链接", current_paper.url)
            
            # 选项卡：分析报告 vs 原始摘要
            tab1, tab2 = st.tabs(["📊 深度分析报告", "📝 原始摘要"])
            
            with tab1:
                if current_paper.analysis_report:
                    st.markdown(current_paper.analysis_report)
                else:
                    st.info("🚧 该论文尚未生成详细报告 (等待 Analyst Agent 处理...)")
                    # 这里可以加一个手动触发按钮
                    # if st.button("立即分析"): ...
            
            with tab2:
                st.write(current_paper.abstract)