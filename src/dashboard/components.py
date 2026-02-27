# src/dashboard/components.py
"""纯函数 HTML 渲染组件（学术风格）。

所有函数只返回 HTML 字符串，不调用任何 st.* 方法。
调用方通过 st.markdown(html, unsafe_allow_html=True) 注入页面。
"""
from __future__ import annotations

from src.dashboard.theme import (
    ELSEVIER_COLORS,
    SCORE_COLOR_NONE,
    SCORE_COLORS,
    SOURCE_COLORS,
    SOURCE_LABELS,
)


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


def source_label(source: str) -> str:
    """返回人类可读的来源标签（用于 sidebar 等非 HTML 场景）。"""
    if source in SOURCE_LABELS:
        return SOURCE_LABELS[source]
    if source.startswith("elsevier:"):
        return source[len("elsevier:"):]
    return source


# ============================
# HTML 片段渲染
# ============================

def render_source_badge(source: str) -> str:
    if source in SOURCE_COLORS:
        color = SOURCE_COLORS[source]
        label = SOURCE_LABELS.get(source, source)
    elif source.startswith("elsevier:"):
        label = source[len("elsevier:"):]
        color = ELSEVIER_COLORS[hash(source) % len(ELSEVIER_COLORS)]
    else:
        color = "#6B6B73"
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
        return '<span class="score-badge" style="background:#A0A0A8;">N/A</span>'
    color = get_score_color(score)
    return f'<span class="score-badge" style="background:{color};">{score}/10</span>'


def render_score_bar(score) -> str:
    """渲染详情面板的评分条。"""
    if score is None:
        return (
            '<div class="score-bar-container">'
            '<span class="score-bar-label" style="color:#A0A0A8;">Score: N/A</span>'
            '</div>'
        )
    filled_color = get_score_color(score)
    empty_color = "#E5E2DC"
    segments = "".join(
        f'<span class="score-bar-segment" style="background:{filled_color if i <= score else empty_color};"></span>'
        for i in range(1, 11)
    )
    return (
        f'<div class="score-bar-container">'
        f'{segments}'
        f'<span class="score-bar-label" style="color:{filled_color};">{score}/10</span>'
        f'</div>'
    )


def render_bookmark_star(is_bookmarked: bool) -> str:
    if is_bookmarked:
        return '<span class="bookmark-star" title="Bookmarked">&#9733;</span>'
    return ""


# ============================
# 页面区块模板
# ============================

def render_hero_header() -> str:
    """顶部品牌横幅 — 学术风格。"""
    return """
    <div style="
        background: #1B2A4A;
        padding: 1.75rem 2rem;
        border-radius: 6px;
        margin-bottom: 2rem;
        border-bottom: 3px solid #B8860B;
    ">
        <h1 style="
            color: #FAF8F5;
            margin: 0;
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1.75rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        ">PaperFlow.AI</h1>
        <p style="
            color: rgba(250, 248, 245, 0.7);
            margin: 0.35rem 0 0 0;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            font-weight: 400;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        ">Intelligent Research Assistant</p>
    </div>
    """


def render_paper_list_header(count: int) -> str:
    """论文列表区域的标题。"""
    return f"""
    <div style="
        padding: 0.6rem 0;
        border-bottom: 2px solid #B8860B;
        margin-bottom: 1.25rem;
    ">
        <h4 style="
            margin: 0;
            color: #1B2A4A;
            font-family: 'Inter', sans-serif;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        ">Papers <span style='font-weight:400; color:#6B6B73;'>({count})</span></h4>
    </div>
    """


def render_paper_card_row(
    *,
    is_selected: bool,
    dot: str,
    badge: str,
    score_badge: str,
    star: str,
    date_str: str,
) -> str:
    """论文卡片的第一行：选中指示 + 状态点 + 来源 + 评分 + 收藏 + 日期。"""
    selector = '<span style="color:#B8860B;font-weight:600;">&#9656; </span>' if is_selected else ""
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">'
        f'<div>{selector}{dot}{badge} {score_badge}{star}</div>'
        f'<span style="color:#A0A0A8;font-size:0.72rem;font-family:Inter,sans-serif;white-space:nowrap;">{date_str}</span>'
        f'</div>'
    )


def render_detail_title(title: str) -> str:
    """详情面板标题区域 — 学术风格。"""
    return f"""
    <div style="
        padding: 1.25rem 1.5rem;
        background: transparent;
        border-left: 3px solid #B8860B;
        margin-bottom: 1.5rem;
    ">
        <h3 style="
            margin: 0;
            color: #1B2A4A;
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1.35rem;
            font-weight: 600;
            line-height: 1.4;
        ">{title}</h3>
    </div>
    """


def render_detail_metadata(
    *,
    badge_html: str,
    date_str: str,
    doi: str | None,
    score_bar_html: str,
    authors_str: str,
) -> str:
    """详情面板的元数据卡片 — 学术风格。"""
    doi_chip = f'<span class="meta-chip">DOI: {doi}</span>' if doi else ""
    return f"""
    <div style="
        background: #FAF8F5;
        border: 1px solid #E5E2DC;
        border-radius: 6px;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
    ">
        <div style="margin-bottom: 0.75rem;">
            {badge_html}
            <span class="meta-chip">{date_str}</span>
            {doi_chip}
        </div>
        <div style="margin-bottom: 0.75rem;">
            {score_bar_html}
        </div>
        <div style="
            font-size: 0.82rem;
            color: #4A4A4F;
            font-family: 'Inter', sans-serif;
            line-height: 1.5;
        "><strong style="color:#1B2A4A;">Authors:</strong> {authors_str}</div>
    </div>
    """
