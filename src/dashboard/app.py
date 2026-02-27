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
    toggle_bookmark, get_distinct_sources,
)
from src.dashboard.config import init_config_form
from src.dashboard.styles import inject_css
from src.dashboard.components import (
    render_hero_header,
    render_source_badge, render_status_dot, render_score_badge,
    render_score_bar, render_bookmark_star, source_label,
    render_paper_list_header, render_paper_card_row,
    render_detail_title, render_detail_metadata,
)

import streamlit as st
from pathlib import Path

# ============================
# 页面配置 & 样式注入
# ============================
st.set_page_config(page_title="PaperFlow.AI", layout="wide", page_icon="🚀")
inject_css()

# ============================
# 初始化
# ============================
st.markdown(render_hero_header(), unsafe_allow_html=True)

initialize_database()

if not check_database_initialized():
    init_config_form()
    st.stop()

# --- session_state ---
if "processed_uploads" not in st.session_state:
    st.session_state.processed_uploads = set()
if "analyzing_papers" not in st.session_state:
    st.session_state.analyzing_papers = {}
if "selected_paper_id" not in st.session_state:
    st.session_state.selected_paper_id = None


# ============================
# Sidebar
# ============================
with st.sidebar:
    st.markdown("### 🔍 Filter and Sort")

    all_sources = get_distinct_sources()
    filter_source = st.multiselect(
        "Source Platforms", options=all_sources, default=[], format_func=source_label,
    )
    show_only_relevant = st.checkbox("Show only high relevance (Relevant)", value=True)
    show_bookmarked_only = st.checkbox("⭐ Show only bookmarks", value=False)
    sort_by = st.selectbox("Sort By", ["Sort by date", "Sort by score"], index=0)
    sort_key = "score" if sort_by == "Sort by score" else "date"

    st.divider()

    # --- PDF Upload ---
    st.markdown("### 📤 Upload PDF Papers")
    uploaded_files = st.file_uploader("Select PDF files", type="pdf", accept_multiple_files=True)

    new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_uploads]

    if new_files:
        data_dir = os.path.join(os.path.dirname(__file__), "../../data")
        Path(data_dir).mkdir(parents=True, exist_ok=True)

        submitted = 0
        with st.spinner(f"Extracting metadata for {len(new_files)} papers..."):
            for uf in new_files:
                st.session_state.processed_uploads.add(uf.name)
                file_path = os.path.join(data_dir, uf.name)
                with open(file_path, "wb") as f:
                    f.write(uf.getbuffer())

                result = process_uploaded_pdf(file_path)
                if "error" in result:
                    st.error(f"{uf.name}: {result['error']}")
                    st.session_state.processed_uploads.discard(uf.name)
                else:
                    paper_id = result["paper_id"]
                    start_background_analysis(paper_id, file_path)
                    st.session_state.analyzing_papers[paper_id] = file_path
                    submitted += 1

        if submitted > 0:
            st.success(f"Metadata extraction complete, {submitted} papers submitted for background analysis (max 3 in parallel)")
            st.rerun()

    # --- 后台分析任务状态 ---
    if st.session_state.analyzing_papers:
        st.divider()
        st.markdown("### ⏳ Background Analysis Tasks")
        completed = []
        for pid in list(st.session_state.analyzing_papers.keys()):
            status = get_analysis_status(pid)
            if status == "running":
                st.info(f"Analyzing: `{pid}`")
            elif status == "done":
                st.success(f"Analysis complete: `{pid}`")
                clear_analysis_status(pid)
                completed.append(pid)
            elif status == "error":
                st.error(f"Analysis failed: `{pid}`")
                clear_analysis_status(pid)
                completed.append(pid)
            else:
                completed.append(pid)
        for pid in completed:
            st.session_state.analyzing_papers.pop(pid, None)

    st.divider()
    st.caption("Data updates automatically every 24 hours")


# ============================
# 主内容区
# ============================
papers = load_papers(
    show_only_relevant=show_only_relevant,
    filter_sources=filter_source,
    sort_by=sort_key,
    show_bookmarked_only=show_bookmarked_only,
)

if not papers:
    st.info("No data available. Please run `main_demo.py` to fetch papers, or upload PDFs in the sidebar.")
else:
    if st.session_state.selected_paper_id not in [p.id for p in papers]:
        st.session_state.selected_paper_id = papers[0].id

    col_list, col_detail = st.columns([2, 5])

    # ---- 左栏: 论文卡片列表 ----
    with col_list:
        st.markdown(render_paper_list_header(len(papers)), unsafe_allow_html=True)

        with st.container(height=650):
            for paper in papers:
                is_selected = (paper.id == st.session_state.selected_paper_id)

                with st.container(border=True):
                    row_html = render_paper_card_row(
                        is_selected=is_selected,
                        dot=render_status_dot(paper, st.session_state.analyzing_papers),
                        badge=render_source_badge(paper.source),
                        score_badge=render_score_badge(paper.relevance_score),
                        star=render_bookmark_star(paper.is_bookmarked),
                        date_str=paper.published_date.strftime("%Y-%m-%d"),
                    )
                    st.markdown(row_html, unsafe_allow_html=True)

                    display_title = paper.title if len(paper.title) <= 120 else paper.title[:117] + "..."
                    with st.container():
                        st.markdown('<div class="paper-card-btn">', unsafe_allow_html=True)
                        if st.button(display_title, key=f"sel_{paper.id}", use_container_width=True):
                            st.session_state.selected_paper_id = paper.id
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

                    if paper.authors:
                        authors_short = ", ".join(paper.authors[:3])
                        if len(paper.authors) > 3:
                            authors_short += " et al."
                        st.caption(authors_short)

    # ---- 右栏: 论文详情面板 ----
    current_paper = next(p for p in papers if p.id == st.session_state.selected_paper_id)

    with col_detail:
        st.markdown(render_detail_title(current_paper.title), unsafe_allow_html=True)

        col1, col2 = st.columns([5, 2])
        with col2:
            bm_label = "★ Bookmarked" if current_paper.is_bookmarked else "☆ Bookmark"
            bm_type = "primary" if current_paper.is_bookmarked else "secondary"
            if st.button(bm_label, key="toggle_bm", type=bm_type, use_container_width=True):
                toggle_bookmark(current_paper.id)
                st.rerun()

        with st.container(height=650):
            authors_str = ", ".join(current_paper.authors) if current_paper.authors else "Unknown"
            metadata_html = render_detail_metadata(
                badge_html=render_source_badge(current_paper.source),
                date_str=current_paper.published_date.strftime("%Y-%m-%d"),
                doi=current_paper.doi,
                score_bar_html=render_score_bar(current_paper.relevance_score),
                authors_str=authors_str,
            )
            st.markdown(metadata_html, unsafe_allow_html=True)

            if current_paper.url:
                st.link_button("🔗 View Original", current_paper.url)

            st.divider()

            tab1, tab2 = st.tabs(["📊 Deep Analysis Report", "📝 Abstract"])

            with tab1:
                if current_paper.analysis_report:
                    st.markdown(current_paper.analysis_report)
                elif current_paper.id in st.session_state.analyzing_papers:
                    st.info("⏳ This paper is being analyzed in the background. The report will be displayed automatically when complete...")
                else:
                    st.info("🚧 This paper has not yet generated a detailed report (waiting for Analyst Agent to process...)")

            with tab2:
                st.markdown(current_paper.abstract)


# ============================
# 自动刷新 (后台任务运行时)
# ============================
if has_running_tasks():
    time.sleep(10)
    st.rerun()
