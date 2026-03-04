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

# 图表专用色板 — 更高饱和度、更大色相间距，便于区分
CHART_COLORS = {
    "arxiv":        "#C0392B",   # 学术红
    "uploaded_pdf": "#2C3E7B",   # 靛蓝
    "asce":         "#1E8449",   # 翠绿
}

CHART_ELSEVIER_COLORS = [
    "#D4A017",  # 琥珀金
    "#7D3C98",  # 皇家紫
    "#2E86C1",  # 钢蓝
    "#E67E22",  # 赤橙
    "#1ABC9C",  # 松石绿
    "#C0392B",  # 学术红
    "#34495E",  # 石墨
    "#27AE60",  # 翠绿
]

SCORE_COLORS = {
    (9, 10): "#1B4332",  # 深森林绿
    (7, 8):  "#3D7A5F",  # 鼠尾草绿
    (5, 6):  "#B8860B",  # 学术金
    (3, 4):  "#A0522D",  # 赭石
    (1, 2):  "#A63D40",  # 暗红
}
SCORE_COLOR_NONE = "#A0A0A8"  # 暖灰
