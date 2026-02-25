# src/dashboard/app.py
import sys
import os
import time

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.dashboard.database import (
    initialize_database, check_database_initialized, load_papers,
    process_uploaded_pdf, start_background_analysis,
    get_analysis_status, clear_analysis_status, has_running_tasks,
)
from src.dashboard.config import init_config_form

import streamlit as st
from pathlib import Path

# 页面配置
st.set_page_config(page_title="AI Research Agent", layout="wide", page_icon="🎓")

st.title("🎓 自动化学术情报局")
st.caption("Your Best Research Assistant")

# Create database tables on app startup
initialize_database()

# Check if database is initialized
if not check_database_initialized():
    init_config_form()
    st.stop()

# --- 初始化 session_state ---
if "processed_uploads" not in st.session_state:
    st.session_state.processed_uploads = set()
if "analyzing_papers" not in st.session_state:
    st.session_state.analyzing_papers = {}  # paper_id -> file_path

# --- Sidebar: 侧边栏过滤器 ---
with st.sidebar:
    st.header("🔍 筛选控制")
    filter_source = st.multiselect("来源平台", ["arxiv", "sciencedirect", "asce"], default=["arxiv"])
    show_only_relevant = st.checkbox("只看高相关 (Relevant)", value=True)

    st.divider()

    # --- PDF Upload Section ---
    st.header("📤 上传 PDF 论文")
    uploaded_file = st.file_uploader("选择 PDF 文件", type="pdf")

    if uploaded_file is not None and uploaded_file.name not in st.session_state.processed_uploads:
        # 标记为已处理，防止重复上传
        st.session_state.processed_uploads.add(uploaded_file.name)

        # 确保 data 目录存在
        data_dir = os.path.join(os.path.dirname(__file__), "../../data")
        Path(data_dir).mkdir(parents=True, exist_ok=True)

        # 保存上传的 PDF 文件
        file_path = os.path.join(data_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # 解析 PDF 元数据（相对较快，同步执行）
        with st.spinner("正在提取论文元数据..."):
            result = process_uploaded_pdf(file_path)

        if "error" in result:
            st.error(result["error"])
            st.session_state.processed_uploads.discard(uploaded_file.name)
        else:
            paper_id = result["paper_id"]
            st.success("元数据提取完成，后台开始深度分析...")
            # 启动后台分析线程
            start_background_analysis(paper_id, file_path)
            st.session_state.analyzing_papers[paper_id] = file_path
            st.rerun()

    # --- 后台分析任务状态 ---
    if st.session_state.analyzing_papers:
        st.divider()
        st.header("⏳ 后台分析任务")
        completed = []
        for pid in list(st.session_state.analyzing_papers.keys()):
            status = get_analysis_status(pid)
            if status == "running":
                st.info(f"正在分析: `{pid}`")
            elif status == "done":
                st.success(f"分析完成: `{pid}`")
                clear_analysis_status(pid)
                completed.append(pid)
            elif status == "error":
                st.error(f"分析失败: `{pid}`")
                clear_analysis_status(pid)
                completed.append(pid)
            else:
                # 状态丢失（如进程重启），清理
                completed.append(pid)
        for pid in completed:
            st.session_state.analyzing_papers.pop(pid, None)

    st.divider()
    st.info("数据每24小时自动更新。")

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
                elif current_paper.id in st.session_state.analyzing_papers:
                    st.info("⏳ 该论文正在后台分析中，完成后会自动显示报告...")
                else:
                    st.info("🚧 该论文尚未生成详细报告 (等待 Analyst Agent 处理...)")

            with tab2:
                st.write(current_paper.abstract)

# --- 自动刷新：有后台任务运行时每 10 秒自动 rerun ---
if has_running_tasks():
    time.sleep(10)
    st.rerun()
