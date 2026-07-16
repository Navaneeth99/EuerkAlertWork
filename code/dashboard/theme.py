"""Streamlit theme helpers matching the report McKinsey chart style (Calibri, navy)."""

from __future__ import annotations

import streamlit as st

from dashboard.plotly_charts import (
    ACCENT_COLOR,
    FONT_FAMILY,
    GRID_COLOR,
    MUTED_TEXT,
    SUBTITLE_TEXT,
    TEXT_COLOR,
    WITH_PR_COLOR,
)


def apply_report_theme() -> None:
    """Inject CSS so the dashboard uses the same font/colors as the report charts."""
    css = f"""
<style>
html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stSelectbox,
.stMultiSelect, .stSlider, .stCheckbox, .stMetric, .stDataFrame, .stCaption,
button, input, textarea, label {{
  font-family: {FONT_FAMILY} !important;
  color: {TEXT_COLOR};
}}
h1, h2, h3, h4 {{
  font-family: {FONT_FAMILY} !important;
  color: {ACCENT_COLOR} !important;
  font-weight: 700 !important;
}}
.stCaption, .stMarkdown p {{
  color: {SUBTITLE_TEXT};
}}
.stMetric label {{
  color: {MUTED_TEXT} !important;
  font-family: {FONT_FAMILY} !important;
}}
.stMetric [data-testid="stMetricValue"] {{
  color: {ACCENT_COLOR} !important;
  font-family: {FONT_FAMILY} !important;
}}
div[data-testid="stSidebar"] {{
  background-color: #FAFAFA;
  border-right: 1px solid {GRID_COLOR};
}}
div[data-testid="stSidebar"] * {{
  font-family: {FONT_FAMILY} !important;
}}
/* Match report accent for interactive widgets */
.stSlider [data-baseweb="slider"] div[role="slider"] {{
  background-color: {WITH_PR_COLOR} !important;
}}
hr {{
  border-color: {GRID_COLOR} !important;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)
