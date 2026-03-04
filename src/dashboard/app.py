# src/dashboard/app.py
"""PaperFlow.AI — Entry point for the Streamlit dashboard.

Uses st.navigation() (MPA v2) to manage page routing.
All shared UI (CSS, top navbar) is rendered here before pg.run().
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from src.dashboard.styles import inject_css
from src.dashboard.components import render_top_navbar

# ============================
# Page Config (once, for ALL pages)
# ============================
st.set_page_config(page_title="PaperFlow.AI", layout="wide", page_icon="📖")

# ============================
# Define Pages
# ============================
library_page = st.Page("library.py", title="Library", default=True)
pipeline_page = st.Page("pages/pipeline.py", title="Pipeline")
insights_page = st.Page("pages/insights.py", title="Insights")

# ============================
# Navigation (hidden from sidebar — we render our own)
# ============================
pg = st.navigation([library_page, pipeline_page, insights_page], position="hidden")

# ============================
# Shared CSS + Top Navbar (appears on ALL pages)
# ============================
inject_css()
st.markdown(render_top_navbar(current_page_title=pg.title), unsafe_allow_html=True)

# ============================
# Run Selected Page
# ============================
pg.run()
