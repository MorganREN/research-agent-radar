# src/dashboard/styles/__init__.py
from pathlib import Path

import streamlit as st

_STYLES_DIR = Path(__file__).parent


@st.cache_resource
def _read_css_files() -> str:
    """读取 styles/ 目录下所有 .css 文件并拼接为一个字符串。"""
    parts: list[str] = []
    for css_file in sorted(_STYLES_DIR.glob("*.css")):
        parts.append(css_file.read_text(encoding="utf-8"))
    return "\n".join(parts)


def inject_css() -> None:
    """将全部 CSS 注入 Streamlit 页面。"""
    css = _read_css_files()
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
