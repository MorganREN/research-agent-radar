# src/dashboard/pages/insights.py
"""Insights — paper feed grouped by fetch date + interactive charts."""
import sys
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BRISBANE_TZ = ZoneInfo("Australia/Brisbane")
from collections import defaultdict, Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st

from src.dashboard.database import load_all_papers, initialize_database
from src.dashboard.components import (
    render_source_badge,
    render_score_badge,
    render_bookmark_star,
    source_label,
)
from src.dashboard.theme import CHART_COLORS, CHART_ELSEVIER_COLORS
import plotly.graph_objects as go

initialize_database()

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
    .feed-abstract-expand summary {
        list-style: none;
        cursor: pointer;
    }
    .feed-abstract-expand summary::-webkit-details-marker { display: none; }
    .feed-abstract-expand summary .abstract-expanded { display: none; }
    .feed-abstract-expand[open] summary .abstract-collapsed { display: none; }
    .feed-abstract-expand[open] summary .abstract-expanded { display: inline; }
    .feed-abstract-toggle {
        color: #B8860B;
        font-size: 0.75rem;
        font-style: italic;
        margin-left: 0.25rem;
    }
    .feed-stats {
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        color: #1B2A4A;
        background: #FAF8F5;
        border: 1px solid #E5E2DC;
        border-radius: 6px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================
# 标题
# ============================
st.markdown("## Insights")
st.caption("Papers grouped by fetch date, with source statistics")


# ============================
# 图表配色辅助
# ============================
def _source_color(src: str) -> str:
    """为来源返回一个图表色板颜色（高区分度）。"""
    if src in CHART_COLORS:
        return CHART_COLORS[src]
    if src.startswith("elsevier:"):
        return CHART_ELSEVIER_COLORS[hash(src) % len(CHART_ELSEVIER_COLORS)]
    return "#6B6B73"


def _short_source(src: str) -> str:
    """缩短来源名称用于图表标签。"""
    if src.startswith("elsevier:"):
        return src[len("elsevier:"):]
    return source_label(src)


# ============================
# 图表绘制
# ============================
def plotly_daily_bar_line(grouped: dict[str, list], all_sources: list[str]):
    """每日论文数量堆叠柱状图 + 总量折线趋势 — Plotly 交互。"""
    sorted_days = sorted(grouped.keys())
    if not sorted_days:
        return None

    fig = go.Figure()

    # 堆叠柱状图 — 每个来源一层
    for src in all_sources:
        counts = [sum(1 for p in grouped[d] if p.source == src) for d in sorted_days]
        if sum(counts) == 0:
            continue
        fig.add_trace(go.Bar(
            x=sorted_days,
            y=counts,
            name=_short_source(src),
            marker_color=_source_color(src),
            hovertemplate="%{x}<br><b>" + _short_source(src) + "</b>: %{y}<extra></extra>",
        ))

    # 总量折线趋势
    daily_totals = [len(grouped[d]) for d in sorted_days]
    fig.add_trace(go.Scatter(
        x=sorted_days,
        y=daily_totals,
        mode="lines+markers",
        name="Total",
        line=dict(color="#B8860B", width=2.5),
        marker=dict(size=5, color="#B8860B"),
        hovertemplate="%{x}<br><b>Total</b>: %{y}<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="Daily Paper Intake",
            font=dict(size=15, family="Playfair Display, Georgia, serif", color="#1B2A4A"),
            x=0.5,
            xanchor="center",
        ),
        showlegend=False,
        paper_bgcolor="#FAF8F5",
        plot_bgcolor="#FAF8F5",
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=10, family="Inter, sans-serif", color="#6B6B73"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#E5E2DC",
            gridwidth=0.5,
            tickfont=dict(size=10, family="Inter, sans-serif", color="#6B6B73"),
            title=None,
            dtick=max(1, max(daily_totals) // 5) if daily_totals else 1,
        ),
        margin=dict(t=50, b=30, l=30, r=10),
        height=350,
    )

    return fig


def plotly_source_pie(papers: list, title: str = "All Sources", center_label: str = "papers"):
    """来源分布交互饼图 — Plotly，悬浮显示来源和数量。"""
    counter = Counter()
    for p in papers:
        counter[p.source] += 1
    if not counter:
        return None

    labels = list(counter.keys())
    sizes = list(counter.values())
    colors = [_source_color(s) for s in labels]
    short_labels = [_short_source(s) for s in labels]

    fig = go.Figure(data=[go.Pie(
        labels=short_labels,
        values=sizes,
        hole=0.45,
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>Papers: %{value}<br>Share: %{percent}<extra></extra>",
    )])

    total = sum(sizes)
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=15, family="Playfair Display, Georgia, serif", color="#1B2A4A"),
            x=0.5,
            xanchor="center",
        ),
        annotations=[dict(
            text=f"<b>{total}</b><br><span style='font-size:11px;color:#6B6B73'>{center_label}</span>",
            x=0.5, y=0.5, font=dict(size=20, family="Playfair Display, serif", color="#1B2A4A"),
            showarrow=False,
        )],
        showlegend=False,
        paper_bgcolor="#FAF8F5",
        plot_bgcolor="#FAF8F5",
        margin=dict(t=50, b=10, l=20, r=20),
        height=350,
    )

    return fig


# ============================
# 侧栏筛选
# ============================
with st.sidebar:
    st.markdown("### Feed Options")
    show_abstract = st.checkbox("Show abstracts", value=True)
    filter_relevant = st.checkbox("Relevant only", value=True)

    all_papers = load_all_papers()

    available_sources = sorted({p.source for p in all_papers})
    feed_source_filter = st.multiselect(
        "Source", options=available_sources, default=[], format_func=source_label,
    )

# ============================
# 筛选和分组
# ============================
papers = all_papers

if filter_relevant:
    papers = [p for p in papers if p.is_relevant]

if feed_source_filter:
    papers = [p for p in papers if p.source in feed_source_filter]

if not papers:
    st.info("No papers found. Run the pipeline to discover new papers.")
    st.stop()

# 按 fetched_date 分组
grouped: dict[str, list] = defaultdict(list)
for p in papers:
    key = p.fetched_date.strftime("%Y-%m-%d") if p.fetched_date else "Unknown"
    grouped[key].append(p)

sorted_days = sorted(grouped.keys(), reverse=True)

# ============================
# 汇总统计
# ============================
total = len(papers)
today_key = datetime.now(BRISBANE_TZ).strftime("%Y-%m-%d")
today_count = len(grouped.get(today_key, []))

st.markdown(
    f'<div class="feed-stats">'
    f'Total: <strong>{total}</strong> papers across <strong>{len(sorted_days)}</strong> days '
    f'&nbsp;&middot;&nbsp; Today: <strong>{today_count}</strong> new'
    f'</div>',
    unsafe_allow_html=True,
)

# ============================
# 图表区
# ============================
all_sources_in_data = sorted({p.source for p in papers})
today_papers = grouped.get(today_key, [])

col_chart1, col_chart2, col_chart3 = st.columns([3, 1, 1])

with col_chart1:
    fig_bar = plotly_daily_bar_line(grouped, all_sources_in_data)
    if fig_bar:
        st.plotly_chart(fig_bar, use_container_width=True)

with col_chart2:
    fig_pie_all = plotly_source_pie(papers, title="All Sources", center_label="total")
    if fig_pie_all:
        st.plotly_chart(fig_pie_all, use_container_width=True)

with col_chart3:
    if today_papers:
        fig_pie_today = plotly_source_pie(today_papers, title="Today", center_label="today")
        if fig_pie_today:
            st.plotly_chart(fig_pie_today, use_container_width=True)
    else:
        st.caption("No papers fetched today.")

st.divider()

# ============================
# 按日渲染论文列表
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
            if len(p.abstract) > 250:
                short = p.abstract[:250] + "..."
                abstract_html = (
                    f'<details class="feed-abstract-expand">'
                    f'<summary class="feed-abstract">'
                    f'<span class="abstract-collapsed">{short} <span class="feed-abstract-toggle">&#9656; show more</span></span>'
                    f'<span class="abstract-expanded">{p.abstract} <span class="feed-abstract-toggle">&#9652; show less</span></span>'
                    f'</summary>'
                    f'</details>'
                )
            else:
                abstract_html = f'<div class="feed-abstract">{p.abstract}</div>'

        relevance_tag = ""
        if p.is_relevant is True:
            relevance_tag = ' &middot; <span style="color:#3D7A5F;">Relevant</span>'
        elif p.is_relevant is False:
            relevance_tag = ' &middot; <span style="color:#A0A0A8;">Not relevant</span>'

        pub_date = p.published_date.strftime("%Y-%m-%d") if p.published_date else ""

        st.markdown(
            f'<div class="feed-card">'
            f'<div class="feed-title"><a {url_attr}>{p.title}</a></div>'
            f'<div class="feed-meta">'
            f'{badge} {score}{star} &nbsp;&middot;&nbsp; {authors_str}'
            f' &nbsp;&middot;&nbsp; Published: {pub_date}'
            f'{relevance_tag}'
            f'</div>'
            f'{abstract_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
