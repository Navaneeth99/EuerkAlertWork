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
import sys
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

import dashboard.report_data as _report_data  # noqa: E402
import utils.impact_analysis as _impact_analysis  # noqa: E402

importlib.reload(_impact_analysis)
importlib.reload(_report_data)
from dashboard.report_data import (  # noqa: E402
    build_report_payload,
    render_report_html,
)
from dashboard.theme import apply_report_theme  # noqa: E402
from utils.impact_analysis import (  # noqa: E402
    fit_coefficient_forest,
    impute_mention_zeros,
    load_cached_coefficients_for_categories,
    load_paper_df_from_cache,
)

st.set_page_config(
    page_title="Press Release Impact",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_report_theme()


@st.cache_data(show_spinner="Loading dashboard cache…")
def cached_load_paper_df(parquet_path: str) -> pd.DataFrame:
    return load_paper_df_from_cache(Path(parquet_path))


@st.cache_data(show_spinner="Fitting fixed-effects models…")
def cached_fit_coefficients(df: pd.DataFrame, fe_col: str) -> pd.DataFrame:
    return fit_coefficient_forest(df, fe_col=fe_col)


@st.cache_data
def cached_read_coef_for_categories(
    categories: tuple[str, ...],
    dashboard_dir: str,
    fe: str,
) -> pd.DataFrame | None:
    return load_cached_coefficients_for_categories(
        list(categories),
        out_dir=Path(dashboard_dir),
        fe=fe,
    )


@st.cache_data
def load_report_assets(template_mtime: float, dclogic_mtime: float) -> tuple[str, str]:
    template = REPORT_TEMPLATE.read_text(encoding="utf-8")
    dclogic = DCLOGIC_JS.read_text(encoding="utf-8")
    return template, dclogic


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

    try:
        paper_df = cached_load_paper_df(str(DEFAULT_PAPER_PARQUET))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load dashboard cache: {exc}")
        st.stop()

    # Older parquet caches predate last-author / field enrichment.
    for col in ("last_author_id", "last_author_name", "field_id", "field_name"):
        if col not in paper_df.columns:
            paper_df[col] = ""

    paper_df = impute_mention_zeros(paper_df)
    if paper_df.empty:
        st.warning("Dashboard cache has no papers.")
        st.stop()

    categories = sorted(
        c for c in paper_df["category"].dropna().unique().tolist() if c
    )
    cats_key = tuple(categories)
    try:
        coef_df = cached_read_coef_for_categories(
            cats_key, str(DEFAULT_DASHBOARD_DIR), "entity"
        )
        university_coef_df = cached_read_coef_for_categories(
            ("institution",), str(DEFAULT_DASHBOARD_DIR), "entity"
        )
        journal_coef_df = cached_read_coef_for_categories(
            ("journal",), str(DEFAULT_DASHBOARD_DIR), "entity"
        )
        field_coef_df = cached_read_coef_for_categories(
            cats_key, str(DEFAULT_DASHBOARD_DIR), "field"
        )
        last_author_coef_df = cached_read_coef_for_categories(
            cats_key, str(DEFAULT_DASHBOARD_DIR), "last_author"
        )
    except TypeError as exc:
        # Stale module / cache from before fe= support — fall back to entity only.
        st.warning(f"Coefficient cache loader mismatch ({exc}); using entity FE only.")
        from utils.impact_analysis import load_cached_coefficients_for_categories as _load

        coef_df = _load(list(cats_key), out_dir=DEFAULT_DASHBOARD_DIR)
        university_coef_df = _load(["institution"], out_dir=DEFAULT_DASHBOARD_DIR)
        journal_coef_df = _load(["journal"], out_dir=DEFAULT_DASHBOARD_DIR)
        field_coef_df = _load(list(cats_key), out_dir=DEFAULT_DASHBOARD_DIR, fe="field")
        last_author_coef_df = None

    n_with = int(paper_df["has_pr"].sum())
    n_without = len(paper_df) - n_with
    n_entities = int(paper_df["entity_name"].nunique())
    n_authors = 0
    n_fields = 0
    if "last_author_id" in paper_df.columns:
        n_authors = int(
            paper_df.loc[
                paper_df["last_author_id"].astype(str).str.len() > 0, "last_author_id"
            ].nunique()
        )
    if "field_id" in paper_df.columns:
        n_fields = int(
            paper_df.loc[paper_df["field_id"].astype(str).str.len() > 0, "field_id"].nunique()
        )

    can_fit = (
        len(paper_df) >= 50
        and n_with >= 5
        and n_without >= 5
    )
    if coef_df is None and can_fit and n_entities >= 2:
        try:
            coef_df = cached_fit_coefficients(paper_df, "entity_name")
        except Exception:  # noqa: BLE001
            coef_df = None
    if university_coef_df is None and can_fit:
        inst = paper_df.loc[paper_df["category"] == "institution"]
        if len(inst) >= 50 and inst["entity_name"].nunique() >= 2:
            try:
                university_coef_df = cached_fit_coefficients(inst, "entity_name")
            except Exception:  # noqa: BLE001
                university_coef_df = None
    if journal_coef_df is None and can_fit:
        jour = paper_df.loc[paper_df["category"] == "journal"]
        if len(jour) >= 50 and jour["entity_name"].nunique() >= 2:
            try:
                journal_coef_df = cached_fit_coefficients(jour, "entity_name")
            except Exception:  # noqa: BLE001
                journal_coef_df = None
    if field_coef_df is None and can_fit and n_fields >= 2:
        try:
            field_coef_df = cached_fit_coefficients(paper_df, "field_id")
        except Exception:  # noqa: BLE001
            field_coef_df = None
    if last_author_coef_df is None and can_fit and n_authors >= 2:
        try:
            last_author_coef_df = cached_fit_coefficients(paper_df, "last_author_id")
        except Exception:  # noqa: BLE001
            last_author_coef_df = None

    payload = build_report_payload(
        paper_df,
        coef_df,
        university_coef_df=university_coef_df,
        journal_coef_df=journal_coef_df,
        field_coef_df=field_coef_df,
        last_author_coef_df=last_author_coef_df,
    )
    template, dclogic = load_report_assets(
        REPORT_TEMPLATE.stat().st_mtime,
        DCLOGIC_JS.stat().st_mtime,
    )
    html = render_report_html(template, dclogic, payload)
    # Viewport-tall iframe; document scrolls inside (nav + full report including conclusion).
    components.html(html, height=900, scrolling=True)


if __name__ == "__main__":
    main()
