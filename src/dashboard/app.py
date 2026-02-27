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

import streamlit as st
from pathlib import Path

# 页面配置
st.set_page_config(page_title="PaperFlow.AI", layout="wide", page_icon="🚀")

# ============================
# 常量
# ============================
SOURCE_COLORS = {
    "arxiv": "#B71C1C",
    "uploaded_pdf": "#1565C0",
    "asce": "#2E7D32",
}

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "uploaded_pdf": "PDF Upload",
    "asce": "ASCE",
}

# Palette for dynamically-assigned elsevier journal colors
ELSEVIER_COLORS = ["#E65100", "#6A1B9A", "#00695C", "#AD1457", "#283593", "#4E342E", "#37474F", "#0277BD"]

SCORE_COLORS = {
    (9, 10): "#1B5E20",  # Deep green
    (7, 8):  "#4CAF50",  # Green
    (5, 6):  "#F9A825",  # Yellow
    (3, 4):  "#E65100",  # Orange
    (1, 2):  "#C62828",  # Red
}
SCORE_COLOR_NONE = "#9E9E9E"  # Gray


# ============================
# Custom CSS
# ============================
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }

    /* ---- 来源 badge ---- */
    .source-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        color: white;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }

    /* ---- 状态圆点 ---- */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
    }
    .status-analyzed  { background-color: #4CAF50; }
    .status-analyzing { background-color: #FF9800; animation: pulse 1.5s infinite; }
    .status-pending   { background-color: #BDBDBD; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50%      { opacity: 0.4; }
    }

    /* ---- 论文卡片按钮: 去除默认按钮样式 ---- */
    .paper-card-btn button {
        background: none !important;
        border: none !important;
        text-align: left !important;
        font-weight: 600 !important;
        color: #1a1a2e !important;
        padding: 4px 0 !important;
        font-size: 0.9rem !important;
        line-height: 1.35 !important;
        white-space: normal !important;
        word-wrap: break-word !important;
    }
    .paper-card-btn button:hover {
        color: #1976D2 !important;
    }
    .paper-card-btn button:focus {
        box-shadow: none !important;
    }

    /* ---- 详情面板 metadata 行 ---- */
    .meta-chip {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 0.78rem;
        margin-right: 6px;
        margin-bottom: 4px;
        background: #F5F5F5;
        color: #424242;
        border: 1px solid #E0E0E0;
    }

    /* ---- 评分 badge ---- */
    .score-badge {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        color: white;
        margin-left: 4px;
        vertical-align: middle;
    }

    /* ---- 收藏星标 ---- */
    .bookmark-star {
        color: #FFC107;
        font-size: 0.85rem;
        margin-left: 4px;
        vertical-align: middle;
    }

    /* ---- 详情面板评分条 ---- */
    .score-bar-container {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 8px;
    }
    .score-bar-segment {
        width: 18px;
        height: 10px;
        border-radius: 2px;
        display: inline-block;
    }
    .score-bar-label {
        font-size: 0.85rem;
        font-weight: 700;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ============================
# 辅助函数
# ============================
def get_score_color(score) -> str:
    if score is None:
        return SCORE_COLOR_NONE
    for (lo, hi), color in SCORE_COLORS.items():
        if lo <= score <= hi:
            return color
    return SCORE_COLOR_NONE


def render_source_badge(source: str) -> str:
    if source in SOURCE_COLORS:
        color = SOURCE_COLORS[source]
        label = SOURCE_LABELS.get(source, source)
    elif source.startswith("elsevier:"):
        label = source[len("elsevier:"):]
        color = ELSEVIER_COLORS[hash(source) % len(ELSEVIER_COLORS)]
    else:
        color = "#757575"
        label = source
    return f'<span class="source-badge" style="background:{color};">{label}</span>'


def render_status_dot(paper, analyzing_set: dict) -> str:
    if paper.analysis_report:
        return '<span class="status-dot status-analyzed" title="Analyzed"></span>'
    elif paper.id in analyzing_set:
        return '<span class="status-dot status-analyzing" title="Analyzing"></span>'
    else:
        return '<span class="status-dot status-pending" title="Pending analysis"></span>'


def render_score_badge(score) -> str:
    if score is None:
        return '<span class="score-badge" style="background:#9E9E9E;">N/A</span>'
    color = get_score_color(score)
    return f'<span class="score-badge" style="background:{color};">{score}/10</span>'


def render_score_bar(score) -> str:
    """渲染详情面板的评分条。"""
    if score is None:
        return '<div class="score-bar-container"><span class="score-bar-label" style="color:#9E9E9E;">Score: N/A</span></div>'
    filled_color = get_score_color(score)
    empty_color = "#E0E0E0"
    segments = ""
    for i in range(1, 11):
        c = filled_color if i <= score else empty_color
        segments += f'<span class="score-bar-segment" style="background:{c};"></span>'
    return (
        f'<div class="score-bar-container">'
        f'{segments}'
        f'<span class="score-bar-label" style="color:{filled_color};">{score}/10</span>'
        f'</div>'
    )


def render_bookmark_star(is_bookmarked: bool) -> str:
    if is_bookmarked:
        return '<span class="bookmark-star" title="Bookmarked">★</span>'
    return ""


# ============================
# 初始化
# ============================
st.markdown("## 🚀 PaperFlow.AI")
st.caption("Intelligent Research Assistant")

initialize_database()

if not check_database_initialized():
    init_config_form()
    st.stop()

# --- 初始化 session_state ---
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
    st.header("🔍 Filter and Sort")

    def _source_label(s: str) -> str:
        if s in SOURCE_LABELS:
            return SOURCE_LABELS[s]
        if s.startswith("elsevier:"):
            return s[len("elsevier:"):]
        return s

    all_sources = get_distinct_sources()
    filter_source = st.multiselect("Source Platforms", options=all_sources, default=[], format_func=_source_label)
    show_only_relevant = st.checkbox("Show only high relevance (Relevant)", value=True)
    show_bookmarked_only = st.checkbox("⭐ Show only bookmarks", value=False)
    sort_by = st.selectbox("Sort By", ["Sort by date", "Sort by score"], index=0)
    sort_key = "score" if sort_by == "Sort by score" else "date"

    st.divider()

    # --- PDF Upload ---
    st.header("📤 Upload PDF Papers")
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
        st.markdown("##### ⏳ Background Analysis Tasks")
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
    # 如果没有选中论文或选中的论文不在列表中，默认选第一篇
    if st.session_state.selected_paper_id not in [p.id for p in papers]:
        st.session_state.selected_paper_id = papers[0].id

    col_list, col_detail = st.columns([2, 5])

    # ---- 左栏: 论文卡片列表 ----
    with col_list:
        st.markdown(f"#### 📄 Paper List ({len(papers)})")

        for paper in papers:
            is_selected = (paper.id == st.session_state.selected_paper_id)

            with st.container(border=True):
                # 第一行: 选中指示 + 状态点 + 来源 badge + 评分 badge + 收藏星 + 日期
                dot = render_status_dot(paper, st.session_state.analyzing_papers)
                badge = render_source_badge(paper.source)
                score_badge = render_score_badge(paper.relevance_score)
                star = render_bookmark_star(paper.is_bookmarked)
                date_str = paper.published_date.strftime("%Y-%m-%d")
                selector = '<span style="color:#1976D2;font-weight:bold;">▸ </span>' if is_selected else ""
                st.markdown(
                    f'{selector}{dot}{badge} {score_badge}{star}'
                    f' <span style="color:#999;font-size:0.75rem;float:right;">{date_str}</span>',
                    unsafe_allow_html=True,
                )

                # 第二行: 论文标题（可点击）
                display_title = paper.title if len(paper.title) <= 120 else paper.title[:117] + "..."
                with st.container():
                    st.markdown('<div class="paper-card-btn">', unsafe_allow_html=True)
                    if st.button(display_title, key=f"sel_{paper.id}", use_container_width=True):
                        st.session_state.selected_paper_id = paper.id
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                # 第三行: 作者（缩略）
                if paper.authors:
                    authors_short = ", ".join(paper.authors[:3])
                    if len(paper.authors) > 3:
                        authors_short += " et al."
                    st.caption(authors_short)

    # ---- 右栏: 论文详情面板 ----
    current_paper = next(p for p in papers if p.id == st.session_state.selected_paper_id)

    with col_detail:
        # 标题行 + 收藏按钮
        title_col, bookmark_col = st.columns([6, 1])
        with title_col:
            st.markdown(f"### {current_paper.title}")
        with bookmark_col:
            bm_label = "★ Bookmarked" if current_paper.is_bookmarked else "☆ Bookmark"
            bm_type = "primary" if current_paper.is_bookmarked else "secondary"
            if st.button(bm_label, key="toggle_bm", type=bm_type, use_container_width=True):
                toggle_bookmark(current_paper.id)
                st.rerun()

        # Metadata chips + 评分条
        authors_str = ", ".join(current_paper.authors) if current_paper.authors else "Unknown"
        date_str = current_paper.published_date.strftime("%Y-%m-%d")
        badge_html = render_source_badge(current_paper.source)

        chips = f'{badge_html}'
        chips += f' <span class="meta-chip">📅 {date_str}</span>'
        if current_paper.doi:
            chips += f' <span class="meta-chip">DOI: {current_paper.doi}</span>'
        st.markdown(chips, unsafe_allow_html=True)

        # 评分条
        st.markdown(render_score_bar(current_paper.relevance_score), unsafe_allow_html=True)

        st.caption(f"**Authors:** {authors_str}")

        # 链接按钮
        if current_paper.url:
            st.link_button("🔗 View Original", current_paper.url)

        st.divider()

        # Tabs
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
