# src/dashboard/pages/2_Daily_Feed.py
import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st

from src.dashboard.styles import inject_css
from src.dashboard.database import load_papers_by_discovered_date, initialize_database
from src.dashboard.components import (
    render_source_badge,
    render_score_badge,
    render_bookmark_star,
    source_label,
)

st.set_page_config(page_title="Daily Feed — PaperFlow.AI", layout="wide", page_icon="📖")

initialize_database()
inject_css()

# ============================
# 页面专用样式
# ============================
st.markdown("""
<style>
    .day-header {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.2rem;
        font-weight: 600;
        color: #1B2A4A;
        padding: 0.5rem 0;
        border-bottom: 2px solid #B8860B;
        margin: 2rem 0 1rem 0;
    }
    .day-header .day-count {
        font-family: 'Inter', sans-serif;
        font-size: 0.75rem;
        font-weight: 400;
        color: #6B6B73;
        margin-left: 0.5rem;
    }
    .feed-card {
        padding: 1rem 1.25rem;
        border: 1px solid #E5E2DC;
        border-radius: 6px;
        margin-bottom: 0.75rem;
        background: #FFFFFF;
        transition: background 0.15s ease;
    }
    .feed-card:hover {
        background: #F5F3EF;
    }
    .feed-title {
        font-family: 'Inter', sans-serif;
        font-size: 0.92rem;
        font-weight: 500;
        color: #1C1C1E;
        line-height: 1.45;
        margin-bottom: 0.4rem;
    }
    .feed-title a {
        color: #1C1C1E;
        text-decoration: none;
    }
    .feed-title a:hover {
        color: #1B2A4A;
    }
    .feed-meta {
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: #6B6B73;
        line-height: 1.4;
    }
    .feed-abstract {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        color: #4A4A4F;
        line-height: 1.55;
        margin-top: 0.5rem;
    }
    .feed-stats {
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        color: #1B2A4A;
        background: #FAF8F5;
        border: 1px solid #E5E2DC;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================
# 页面标题
# ============================
st.markdown("## Daily Feed")
st.caption("Papers grouped by the date they were discovered by the system")

# ============================
# 侧栏筛选
# ============================
with st.sidebar:
    st.markdown("### Feed Options")
    show_abstract = st.checkbox("Show abstracts", value=False)
    filter_relevant = st.checkbox("Relevant only", value=False)

    all_papers = load_papers_by_discovered_date()

    available_sources = sorted({p.source for p in all_papers})
    feed_source_filter = st.multiselect(
        "Source", options=available_sources, default=[], format_func=source_label,
    )

# ============================
# 加载和分组
# ============================
papers = all_papers

if filter_relevant:
    papers = [p for p in papers if p.is_relevant]

if feed_source_filter:
    papers = [p for p in papers if p.source in feed_source_filter]

if not papers:
    st.info("No papers found. Run the pipeline to discover new papers.")
    st.stop()

# 按 discovered_at 日期分组
grouped = defaultdict(list)
for p in papers:
    day_key = p.discovered_at.strftime("%Y-%m-%d")
    grouped[day_key].append(p)

# 按日期降序排列
sorted_days = sorted(grouped.keys(), reverse=True)

# ============================
# 汇总统计
# ============================
total = len(papers)
today_key = datetime.utcnow().strftime("%Y-%m-%d")
today_count = len(grouped.get(today_key, []))

st.markdown(
    f'<div class="feed-stats">'
    f'Total: <strong>{total}</strong> papers across <strong>{len(sorted_days)}</strong> days '
    f'&nbsp;&middot;&nbsp; Today: <strong>{today_count}</strong> new'
    f'</div>',
    unsafe_allow_html=True,
)

# ============================
# 按日渲染
# ============================
for day in sorted_days:
    day_papers = grouped[day]
    label = "Today" if day == today_key else day

    st.markdown(
        f'<div class="day-header">{label}'
        f'<span class="day-count">{len(day_papers)} papers</span></div>',
        unsafe_allow_html=True,
    )

    for p in day_papers:
        badge = render_source_badge(p.source)
        score = render_score_badge(p.relevance_score)
        star = render_bookmark_star(p.is_bookmarked)

        authors_str = ", ".join(p.authors[:3]) if p.authors else "Unknown"
        if p.authors and len(p.authors) > 3:
            authors_str += " et al."

        url_attr = f'href="{p.url}" target="_blank"' if p.url else 'href="#"'

        abstract_html = ""
        if show_abstract and p.abstract:
            short = p.abstract[:250] + "..." if len(p.abstract) > 250 else p.abstract
            abstract_html = f'<div class="feed-abstract">{short}</div>'

        relevance_tag = ""
        if p.is_relevant is True:
            relevance_tag = ' &middot; <span style="color:#3D7A5F;">Relevant</span>'
        elif p.is_relevant is False:
            relevance_tag = ' &middot; <span style="color:#A0A0A8;">Not relevant</span>'

        st.markdown(
            f'<div class="feed-card">'
            f'<div class="feed-title"><a {url_attr}>{p.title}</a></div>'
            f'<div class="feed-meta">'
            f'{badge} {score}{star} &nbsp;&middot;&nbsp; {authors_str}'
            f' &nbsp;&middot;&nbsp; {p.published_date.strftime("%Y-%m-%d")}'
            f'{relevance_tag}'
            f'</div>'
            f'{abstract_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
