# src/dashboard/theme.py
# 主题常量：颜色、标签映射、评分色板

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
ELSEVIER_COLORS = [
    "#E65100", "#6A1B9A", "#00695C", "#AD1457",
    "#283593", "#4E342E", "#37474F", "#0277BD",
]

SCORE_COLORS = {
    (9, 10): "#1B5E20",  # Deep green
    (7, 8):  "#4CAF50",  # Green
    (5, 6):  "#F9A825",  # Yellow
    (3, 4):  "#E65100",  # Orange
    (1, 2):  "#C62828",  # Red
}
SCORE_COLOR_NONE = "#9E9E9E"  # Gray
