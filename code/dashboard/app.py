"""
Press Release Impact Streamlit Dashboard

Interactive dashboard for with-PR vs without-PR Altmetric / citation impact.
Charts reuse the report McKinsey visual design (navy + muted gray-blue, Calibri) via Plotly.

Loads a prebuilt parquet from Processed/dashboard/ (fast). Rebuild with:
    python code/08_export_dashboard_data.py

Usage (from repo root):
    streamlit run code/dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT = CODE_DIR.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

DEFAULT_DASHBOARD_DIR = ROOT / "Processed" / "dashboard"
DEFAULT_PAPER_PARQUET = DEFAULT_DASHBOARD_DIR / "paper_df.parquet"
DEFAULT_DASHBOARD_META = DEFAULT_DASHBOARD_DIR / "meta.json"

from dashboard.plotly_charts import (  # noqa: E402
    forest_plot_plotly,
    grouped_bar_with_error_plotly,
)
from dashboard.theme import apply_report_theme  # noqa: E402
from utils.impact_analysis import (  # noqa: E402
    METRIC_LABELS,
    METRIC_LABEL_MAP,
    METRICS,
    compute_group_stats,
    fit_coefficient_forest,
    impute_mention_zeros,
    load_cached_coefficients_for_categories,
    load_cached_overview_for_categories,
    load_paper_df_from_cache,
    overview_metric_stats,
    short_entity_name,
)

st.set_page_config(
    page_title="Press Release Impact",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_report_theme()


@st.cache_data(show_spinner="Loading dashboard cache…")
def cached_load_paper_df(parquet_path: str) -> pd.DataFrame:
    return load_paper_df_from_cache(Path(parquet_path))


@st.cache_data(show_spinner="Fitting fixed-effects models…")
def cached_fit_coefficients(df: pd.DataFrame) -> pd.DataFrame:
    return fit_coefficient_forest(df)


@st.cache_data
def cached_read_coef_for_categories(
    categories: tuple[str, ...],
    dashboard_dir: str,
) -> pd.DataFrame | None:
    return load_cached_coefficients_for_categories(
        list(categories),
        out_dir=Path(dashboard_dir),
    )


@st.cache_data
def cached_read_overview_for_categories(
    categories: tuple[str, ...],
    dashboard_dir: str,
) -> pd.DataFrame | None:
    return load_cached_overview_for_categories(
        list(categories),
        out_dir=Path(dashboard_dir),
    )


def filter_paper_df(
    paper_df: pd.DataFrame,
    *,
    categories: list[str],
    entities: list[str],
    impute_zeros: bool,
) -> pd.DataFrame:
    out = paper_df.copy()
    if categories:
        out = out[out["category"].isin(categories)]
    if entities:
        out = out[out["entity_name"].isin(entities)]
    if impute_zeros:
        out = impute_mention_zeros(out)
    return out


def render_sidebar(paper_df: pd.DataFrame, meta: dict | None) -> dict:
    st.sidebar.header("Filters")

    if meta:
        created = meta.get("created_at_utc", "")
        n_combos = len(meta.get("category_combos") or [])
        st.sidebar.caption(
            f"Cache: {meta.get('n_papers', len(paper_df)):,} papers"
            + (f" · built {created[:10]}" if created else "")
            + (f" · {n_combos} category combos" if n_combos else "")
        )

    all_categories = sorted(
        c for c in paper_df["category"].dropna().unique().tolist() if c
    )
    categories = st.sidebar.multiselect(
        "Category",
        options=all_categories,
        default=all_categories,
        help=(
            "Filter by OpenAlex entity category. Overview and fixed-effects charts "
            "are pre-cached for every category combination."
        ),
    )

    scoped = paper_df
    if categories:
        scoped = scoped[scoped["category"].isin(categories)]

    entity_counts = scoped.groupby("entity_name").size().sort_values(ascending=False)
    entity_options = entity_counts.index.tolist()
    entity_labels = {
        name: f"{short_entity_name(name)} ({entity_counts[name]:,})"
        for name in entity_options
    }

    selected_entities = st.sidebar.multiselect(
        "Entity",
        options=entity_options,
        default=[],
        format_func=lambda name: entity_labels.get(name, name),
        help="Searchable dropdown — type to filter. Leave empty to include all entities.",
        placeholder="Search entities…",
    )

    impute_zeros = st.sidebar.checkbox(
        "Impute 0 for missing mention fields",
        value=True,
    )

    st.sidebar.caption(
        f"Loaded {len(paper_df):,} papers · "
        f"{int(paper_df['has_pr'].sum()):,} with PR"
    )
    st.sidebar.markdown(
        "Rebuild cache (all category combos):\n"
        "`python code/08_export_dashboard_data.py`"
    )

    return {
        "categories": categories,
        "entities": selected_entities,
        "impute_zeros": impute_zeros,
    }


def format_active_filters(
    *,
    categories: list[str],
    entities: list[str],
) -> str:
    """Short caption describing active sidebar filters for each section."""
    if not categories:
        cat_text = "none selected"
    else:
        cat_text = ", ".join(categories)

    if entities:
        if len(entities) <= 3:
            ent_text = ", ".join(short_entity_name(e) for e in entities)
        else:
            ent_text = (
                ", ".join(short_entity_name(e) for e in entities[:3])
                + f", and {len(entities) - 3} more"
            )
        entity_line = f" Entities: **{ent_text}**."
    else:
        entity_line = " Entities: **all** (no entity filter)."

    return (
        f"**Current filters** — Categories: **{cat_text}**.{entity_line} "
        "Update these from the **sidebar**."
    )


def section_1_performance(
    filtered: pd.DataFrame,
    *,
    categories: list[str],
    entities: list[str],
    overview_stats: pd.DataFrame | None = None,
) -> None:
    st.header("Section 1 — Performance by Metric")
    st.markdown(
        "Compare mean Altmetric / citation outcomes for papers **with** vs **without** "
        "a matched EurekAlert press release. Bars show mean ± SE."
    )
    st.caption(format_active_filters(categories=categories, entities=entities))
    st.markdown(
        "**Attention Score** is a weighted sum of Altmetric mention channels "
        "(following Altmetric’s scoring weights): news ×8, blogs/podcasts ×5, "
        "policy/patents/Wikipedia ×3, and social channels such as X, Facebook, "
        "and Bluesky at lower weights (e.g. ×0.25). Citations are reported "
        "separately and are not included in the Attention Score."
    )

    if filtered.empty:
        st.warning("No papers match the current filters.")
        return

    stats = overview_stats if overview_stats is not None else overview_metric_stats(filtered)
    means_pr, errs_pr, n_pr = [], [], []
    means_no, errs_no, n_no = [], [], []
    for m in METRICS:
        pr = stats[(stats["metric"] == m) & (stats["group"] == "With PR")].iloc[0]
        no = stats[(stats["metric"] == m) & (stats["group"] == "Without PR")].iloc[0]
        means_pr.append(float(pr["mean"]))
        errs_pr.append(float(pr["se"]))
        n_pr.append(int(pr["n"]))
        means_no.append(float(no["mean"]))
        errs_no.append(float(no["se"]))
        n_no.append(int(no["n"]))

    fig = grouped_bar_with_error_plotly(
        METRIC_LABELS,
        [
            ("With PR", means_pr, errs_pr, n_pr),
            ("Without PR", means_no, errs_no, n_no),
        ],
        title="<b>Impact of press release</b>",
        ylabel="Mean Value per Paper",
        label_values=True,
        height=520,
    )
    st.plotly_chart(fig, use_container_width=True)

    table = pd.DataFrame(
        {
            "Metric": METRIC_LABELS,
            "With PR (mean)": means_pr,
            "With PR (SE)": errs_pr,
            "Without PR (mean)": means_no,
            "Without PR (SE)": errs_no,
            "N with PR": n_pr,
            "N without PR": n_no,
        }
    )
    st.dataframe(
        table.style.format(
            {
                "With PR (mean)": "{:.3f}",
                "With PR (SE)": "{:.3f}",
                "Without PR (mean)": "{:.3f}",
                "Without PR (SE)": "{:.3f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def section_3_heterogeneity(
    filtered: pd.DataFrame,
    *,
    categories: list[str],
    entities: list[str],
) -> None:
    st.header("Section 2 — Heterogeneity by Entity")
    st.markdown(
        "Per-entity comparison of with-PR vs without-PR means. "
        "Entities are sorted by paper count (most on the left)."
    )
    st.caption(format_active_filters(categories=categories, entities=entities))

    if filtered.empty:
        st.warning("No papers match the current filters.")
        return

    metric = st.selectbox(
        "Metric",
        options=METRICS,
        format_func=lambda m: METRIC_LABEL_MAP[m],
        index=METRICS.index("attention_score") if "attention_score" in METRICS else 0,
        key="section3_metric",
    )
    metric_label = METRIC_LABEL_MAP[metric]

    n_unique = int(filtered["entity_name"].nunique())
    if n_unique == 0:
        st.warning("No entities available for this filter set.")
        return

    if n_unique == 1:
        max_entities = 1
    else:
        max_entities = st.slider(
            "Max entities to display",
            min_value=1,
            max_value=min(60, n_unique),
            value=min(15, n_unique),
            key="section3_max_entities",
        )

    names, m_pr, e_pr, m_no, e_no, n_pr, n_no = compute_group_stats(
        filtered, "entity_name", metric
    )
    names = names[:max_entities]
    m_pr = m_pr[:max_entities]
    e_pr = e_pr[:max_entities]
    m_no = m_no[:max_entities]
    e_no = e_no[:max_entities]
    n_pr = n_pr[:max_entities]
    n_no = n_no[:max_entities]

    cats = filtered["category"].dropna().unique().tolist()
    entity_label = cats[0].title() if len(cats) == 1 else "Entity"

    fig = grouped_bar_with_error_plotly(
        names,
        [
            ("With PR", m_pr, e_pr, n_pr),
            ("Without PR", m_no, e_no, n_no),
        ],
        title=(
            f"<b>{metric_label} by {entity_label}</b><br>"
            f"<span style='font-size:11px;font-weight:normal;color:#4A4A4A'>"
            f"(sorted by paper count, most on left)</span>"
        ),
        ylabel="Mean Value per Paper",
        height=max(480, 80 + 32 * len(names)),
    )
    st.plotly_chart(fig, use_container_width=True)


def section_4_fixed_effects(
    filtered: pd.DataFrame,
    *,
    categories: list[str],
    entities: list[str],
    coef_df: pd.DataFrame | None = None,
) -> None:
    st.header("Section 3 — Fixed-Effects Estimates")
    st.markdown(
        "OLS coefficient on `has_pr` with **entity fixed effects** "
        "(`metric ~ has_pr | entity_name`, CRV1 SEs clustered by entity)."
    )
    st.caption(format_active_filters(categories=categories, entities=entities))

    n_total = len(filtered)
    n_with = int(filtered["has_pr"].sum()) if n_total else 0
    n_entities = filtered["entity_name"].nunique() if n_total else 0

    if n_total < 50 or n_with < 5 or (n_total - n_with) < 5:
        st.warning(
            "Sample too small for reliable fixed-effects estimates. "
            "Widen entity filters."
        )
        return

    if n_entities < 2:
        st.warning("Need at least two entities for entity fixed effects.")
        return

    if coef_df is None:
        try:
            coef_df = cached_fit_coefficients(filtered)
            st.caption("Fitted on the fly (entity filter active or combo not in cache).")
        except Exception as exc:  # noqa: BLE001 — surface model errors in UI
            st.error(f"Could not fit fixed-effects models: {exc}")
            return
    else:
        st.caption("Loaded from precomputed category-combination cache.")

    fig = forest_plot_plotly(coef_df)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        coef_df.rename(
            columns={
                "metric": "Metric",
                "coef": "Coefficient",
                "se": "SE",
                "ci_lo": "95% CI low",
                "ci_hi": "95% CI high",
            }
        ).style.format(
            {
                "Coefficient": "{:.3f}",
                "SE": "{:.3f}",
                "95% CI low": "{:.3f}",
                "95% CI high": "{:.3f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    st.title("Press Release Impact Dashboard")
    st.caption(
        "EurekAlert! matched papers · OpenAlex citations · Altmetric attention"
    )

    parquet_path = DEFAULT_PAPER_PARQUET
    if not parquet_path.exists():
        st.error(
            f"Dashboard cache not found at `{parquet_path}`.\n\n"
            "Build it once (queries DuckDB + Altmetric), then re-run the app:\n\n"
            "```bash\npython code/08_export_dashboard_data.py\n```"
        )
        st.stop()

    meta: dict | None = None
    if DEFAULT_DASHBOARD_META.exists():
        try:
            meta = json.loads(DEFAULT_DASHBOARD_META.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = None

    try:
        paper_full = cached_load_paper_df(str(parquet_path))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load dashboard cache: {exc}")
        st.stop()

    controls = render_sidebar(paper_full, meta)
    categories = controls["categories"]
    entities = controls["entities"]
    cat_key = tuple(sorted(categories))

    filtered = filter_paper_df(
        paper_full,
        categories=categories,
        entities=entities,
        impute_zeros=controls["impute_zeros"],
    )

    # Precomputed caches assume imputed zeros and no entity filter.
    overview_stats = None
    coef_df = None
    if categories and not entities and controls["impute_zeros"]:
        overview_stats = cached_read_overview_for_categories(
            cat_key, str(DEFAULT_DASHBOARD_DIR)
        )
        coef_df = cached_read_coef_for_categories(
            cat_key, str(DEFAULT_DASHBOARD_DIR)
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Papers (filtered)", f"{len(filtered):,}")
    c2.metric("With PR", f"{int(filtered['has_pr'].sum()) if len(filtered) else 0:,}")
    c3.metric(
        "Without PR",
        f"{int((~filtered['has_pr']).sum()) if len(filtered) else 0:,}",
    )

    section_1_performance(
        filtered,
        categories=categories,
        entities=entities,
        overview_stats=overview_stats,
    )
    st.divider()
    section_3_heterogeneity(
        filtered,
        categories=categories,
        entities=entities,
    )
    st.divider()
    section_4_fixed_effects(
        filtered,
        categories=categories,
        entities=entities,
        coef_df=coef_df,
    )


if __name__ == "__main__":
    main()
