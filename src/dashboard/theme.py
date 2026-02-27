# src/dashboard/theme.py
# 主题常量：颜色、标签映射、评分色板（学术风格 — 降饱和）

SOURCE_COLORS = {
    "arxiv": "#8B2500",        # 砖红
    "uploaded_pdf": "#1B2A4A",  # 深海军蓝
    "asce": "#2D5F3F",         # 深鼠尾草
}

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "uploaded_pdf": "PDF Upload",
    "asce": "ASCE",
}

# Palette for dynamically-assigned elsevier journal colors (muted)
ELSEVIER_COLORS = [
    "#8B4513", "#5B3A6B", "#2D5F3F", "#7A3B4E",
    "#1B2A4A", "#4A3728", "#3A4A52", "#2A5A7A",
]

SCORE_COLORS = {
    (9, 10): "#1B4332",  # 深森林绿
    (7, 8):  "#3D7A5F",  # 鼠尾草绿
    (5, 6):  "#B8860B",  # 学术金
    (3, 4):  "#A0522D",  # 赭石
    (1, 2):  "#A63D40",  # 暗红
}
SCORE_COLOR_NONE = "#A0A0A8"  # 暖灰
