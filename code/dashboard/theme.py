"""Streamlit chrome theme matching the HTML report (#1F4E79 navy)."""

from __future__ import annotations

import streamlit as st

NAVY = "#1F4E79"
NAVY_DARK = "#163A5C"
MUTED = "#5A6A7A"
GRID = "#D5E0EB"
FONT = "'Source Sans 3', Calibri, Arial, sans-serif"


def apply_report_theme() -> None:
    """Inject CSS so Streamlit chrome matches the report template."""
    css = f"""
<style>
html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stSelectbox,
.stMultiSelect, .stSlider, .stCheckbox, .stMetric, .stDataFrame, .stCaption,
button, input, textarea, label {{
  font-family: {FONT} !important;
  color: {NAVY_DARK};
}}
h1, h2, h3, h4 {{
  font-family: {FONT} !important;
  color: {NAVY} !important;
  font-weight: 700 !important;
}}
.stCaption, .stMarkdown p {{
  color: {MUTED};
}}
div[data-testid="stSidebar"] {{
  display: none !important;
}}
section[data-testid="stSidebar"] {{
  display: none !important;
}}
/* Hide collapsed sidebar control */
button[kind="header"] {{
  display: none !important;
}}
[data-testid="collapsedControl"] {{
  display: none !important;
}}
header[data-testid="stHeader"] {{
  background: transparent;
}}
/* Hide iframe chrome from st.components.html */
iframe {{
  border: none !important;
}}
footer {{
  display: none !important;
}}
.block-container {{
  padding-top: 0.5rem !important;
  padding-bottom: 0 !important;
  padding-left: 1rem !important;
  padding-right: 1rem !important;
  max-width: 1200px !important;
}}
hr {{
  border-color: {GRID} !important;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)
