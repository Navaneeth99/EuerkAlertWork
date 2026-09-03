"""
Press Release Impact Streamlit Dashboard

Renders the HTML report template filled with live dashboard-cache data.

Rebuild cache:
    python code/08_export_dashboard_data.py

Usage (from repo root):
    streamlit run code/dashboard/app.py
"""

from __future__ import annotations

import importlib
import os
import sys
import traceback
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT = CODE_DIR.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

DEFAULT_DASHBOARD_DIR = ROOT / "Processed" / "dashboard"
DEFAULT_PAPER_PARQUET = DEFAULT_DASHBOARD_DIR / "paper_df.parquet"
REPORT_TEMPLATE = Path(__file__).resolve().parent / "report_template.html"
DCLOGIC_JS = Path(__file__).resolve().parent / "assets" / "dclogic.js"
REPORT_DATA_PY = Path(__file__).resolve().parent / "report_data.py"

from dashboard.report_data import (  # noqa: E402
    build_report_payload,
    render_report_html,
)
from dashboard.theme import apply_report_theme  # noqa: E402
import utils.impact_analysis as impact_analysis  # noqa: E402

importlib.reload(impact_analysis)

from utils.impact_analysis import (  # noqa: E402
    coef_path_for_categories,
    impute_mention_zeros,
    load_cached_coefficients_for_categories,
    load_paper_df_from_cache,
    optimize_dashboard_memory,
)

# Hosted tiers (Render free ≈512MB RAM) cannot fit pyfixest on 1M+ rows in memory
# and time out on multi-way FE fits. Use precomputed CSVs in Processed/dashboard/.
RUNTIME_FE_FIT = os.environ.get("EUREKALERT_RUNTIME_FE_FIT", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

st.set_page_config(
    page_title="Press Release Impact",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_report_theme()


def _coef_path_mtime(
    categories: tuple[str, ...],
    dashboard_dir: Path,
    fe: str,
) -> float:
    path = coef_path_for_categories(categories, out_dir=dashboard_dir, fe=fe)
    return path.stat().st_mtime if path.exists() else 0.0


def _dashboard_coef_mtime(dashboard_dir: Path) -> str:
    """Fingerprint coefficient CSV mtimes so Streamlit cache refreshes after export."""
    rel_paths = [
        "coefficients/by_category/institution__journal__publisher.csv",
        "coefficients/by_category/institution.csv",
        "coefficients/by_category/institution__journal.csv",
        "coefficients/by_mfe/institution__journal__entity_last_author.csv",
        "coefficient_forest.csv",
    ]
    return ":".join(
        str((dashboard_dir / rel).stat().st_mtime if (dashboard_dir / rel).exists() else 0)
        for rel in rel_paths
    )


@st.cache_data(show_spinner="Loading dashboard cache…")
def cached_load_paper_df(parquet_path: str, parquet_mtime: float) -> pd.DataFrame:
    del parquet_mtime
    paper_df = load_paper_df_from_cache(Path(parquet_path))
    return optimize_dashboard_memory(paper_df)


@st.cache_data
def cached_read_coef_for_categories(
    categories: tuple[str, ...],
    dashboard_dir: str,
    fe: str,
    coef_mtime: float,
) -> pd.DataFrame | None:
    del coef_mtime
    return load_cached_coefficients_for_categories(
        list(categories),
        out_dir=Path(dashboard_dir),
        fe=fe,
    )


@st.cache_data
def load_report_assets(template_mtime: float, dclogic_mtime: float) -> tuple[str, str]:
    del template_mtime, dclogic_mtime
    template = REPORT_TEMPLATE.read_text(encoding="utf-8")
    dclogic = DCLOGIC_JS.read_text(encoding="utf-8")
    return template, dclogic


@st.cache_data(show_spinner="Building report…")
def cached_render_report(
    parquet_mtime: float,
    template_mtime: float,
    dclogic_mtime: float,
    coef_mtime_key: str,
    report_data_mtime: float,
) -> str:
    del parquet_mtime, coef_mtime_key, report_data_mtime
    paper_df = cached_load_paper_df(
        str(DEFAULT_PAPER_PARQUET),
        DEFAULT_PAPER_PARQUET.stat().st_mtime,
    )
    for col in ("last_author_id", "last_author_name", "field_id", "field_name"):
        if col not in paper_df.columns:
            paper_df[col] = ""

    paper_df = impute_mention_zeros(paper_df)
    if paper_df.empty:
        raise ValueError("Dashboard cache has no papers.")

    categories = sorted(
        c for c in paper_df["category"].dropna().unique().tolist() if c
    )
    cats_key = tuple(categories)
    dash = str(DEFAULT_DASHBOARD_DIR)
    coef_df = cached_read_coef_for_categories(
        cats_key,
        dash,
        "entity",
        _coef_path_mtime(cats_key, DEFAULT_DASHBOARD_DIR, "entity"),
    )
    university_coef_df = cached_read_coef_for_categories(
        ("institution",),
        dash,
        "entity",
        _coef_path_mtime(("institution",), DEFAULT_DASHBOARD_DIR, "entity"),
    )
    uj_key = ("institution", "journal")
    univ_jour_coef_df = cached_read_coef_for_categories(
        uj_key,
        dash,
        "entity",
        _coef_path_mtime(uj_key, DEFAULT_DASHBOARD_DIR, "entity"),
    )
    univ_jour_last_author_coef_df = cached_read_coef_for_categories(
        uj_key,
        dash,
        "entity_last_author",
        _coef_path_mtime(uj_key, DEFAULT_DASHBOARD_DIR, "entity_last_author"),
    )

    payload = build_report_payload(
        paper_df,
        coef_df,
        university_coef_df=university_coef_df,
        univ_jour_coef_df=univ_jour_coef_df,
        univ_jour_last_author_coef_df=univ_jour_last_author_coef_df,
    )
    template, dclogic = load_report_assets(template_mtime, dclogic_mtime)
    return render_report_html(template, dclogic, payload)


def main() -> None:
    if not DEFAULT_PAPER_PARQUET.exists():
        st.error(
            f"Dashboard cache not found at `{DEFAULT_PAPER_PARQUET}`.\n\n"
            "Build it once, then re-run the app:\n\n"
            "```bash\npython code/08_export_dashboard_data.py\n```"
        )
        st.stop()

    if not REPORT_TEMPLATE.exists() or not DCLOGIC_JS.exists():
        st.error(
            "Report template assets missing. Expected "
            f"`{REPORT_TEMPLATE.name}` and `assets/dclogic.js`."
        )
        st.stop()

    if RUNTIME_FE_FIT:
        st.warning(
            "EUREKALERT_RUNTIME_FE_FIT is enabled. On hosted tiers this can "
            "exceed memory limits or time out; prefer precomputed CSV caches."
        )

    html = cached_render_report(
        DEFAULT_PAPER_PARQUET.stat().st_mtime,
        REPORT_TEMPLATE.stat().st_mtime,
        DCLOGIC_JS.stat().st_mtime,
        _dashboard_coef_mtime(DEFAULT_DASHBOARD_DIR),
        REPORT_DATA_PY.stat().st_mtime if REPORT_DATA_PY.exists() else 0.0,
    )
    components.html(html, height=900, scrolling=True)


try:
    main()
except Exception:  # noqa: BLE001
    st.error("The dashboard failed to render. Details below.")
    st.code(traceback.format_exc())
