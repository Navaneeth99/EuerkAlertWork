"""Shared data loading and impact metrics for report charts and Streamlit."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT = CODE_DIR.parent
DEFAULT_DUCKDB = ROOT / "Processed" / "eurekalert.duckdb"
DEFAULT_ALTMET_CSV = ROOT / "rawdata" / "AltMetData" / "aaas_deliverable_20260415.csv"
DEFAULT_CITED_CACHE = ROOT / "Processed" / "cited_by_count_cache.json"
DEFAULT_DASHBOARD_DIR = ROOT / "Processed" / "dashboard"
DEFAULT_PAPER_PARQUET = DEFAULT_DASHBOARD_DIR / "paper_df.parquet"
DEFAULT_COEF_CSV = DEFAULT_DASHBOARD_DIR / "coefficient_forest.csv"
DEFAULT_DASHBOARD_META = DEFAULT_DASHBOARD_DIR / "meta.json"

# Columns needed by the Streamlit dashboard (keeps the on-disk file small/fast).
DASHBOARD_COLUMNS = [
    "entity_name",
    "category",
    "doi_norm",
    "publication_date",
    "pub_year",
    "has_pr",
    "patent_mentions",
    "policy_mentions",
    "news_mentions",
    "facebook_mentions",
    "x_post_mentions",
    "bluesky_mentions",
    "video_mentions",
    "cited_by_count",
    "attention_score",
    "total_mentions",
]

MENTION_COLS = [
    "patent_mentions",
    "policy_mentions",
    "news_mentions",
    "facebook_mentions",
    "x_post_mentions",
    "bluesky_mentions",
    "video_mentions",
    "cited_by_count",
]

METRICS = [
    "news_mentions",
    "patent_mentions",
    "facebook_mentions",
    "x_post_mentions",
    "policy_mentions",
    "attention_score",
    "cited_by_count",
]

METRIC_LABELS = [
    "News Mentions",
    "Patent Mentions",
    "Facebook Mentions",
    "X Mentions",
    "Policy Mentions",
    "Attention Score",
    "Citations",
]

METRIC_LABEL_MAP = dict(zip(METRICS, METRIC_LABELS))

ATTENTION_WEIGHTS = {
    "news_mentions": 8,
    "blog_mentions": 5,
    "podcast_mentions": 5,
    "policy_mentions": 3,
    "clinical_guidelines_mentions": 3,
    "patent_mentions": 3,
    "wikipedia_mentions": 3,
    "peer_review_mentions": 1,
    "weibo_mentions": 1,
    "googleplus_mentions": 1,
    "f1000_mentions": 1,
    "syllabi_mentions": 1,
    "linkedin_mentions": 0.5,
    "bluesky_mentions": 0.25,
    "x_post_mentions": 0.25,
    "facebook_mentions": 0.25,
    "reddit_mentions": 0.25,
    "pinterest_mentions": 0.25,
    "qa_mentions": 0.25,
    "video_mentions": 0.25,
}

DEFAULT_SOURCE_NOTE = (
    "Source: OpenAlex, Altmetric, press release data. Bars: mean ± SE."
)

REQUIRED_PIPELINE_OBJECTS = ("embedding_title_match", "pr_paper_matched", "doi_list_norm")


def short_entity_name(name: str) -> str:
    return name.split(",")[0].strip()


def assert_pipeline_objects(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure the matching-pipeline views/tables exist before querying read-only."""
    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables"
        ).fetchall()
    }
    missing = [name for name in REQUIRED_PIPELINE_OBJECTS if name not in existing]
    if missing:
        raise RuntimeError(
            "Missing required DuckDB objects: "
            + ", ".join(missing)
            + ".\nRun the matching pipeline first (analysis.ipynb or "
            "`python code/06_matching_pipeline.py`) so these views/tables are saved "
            "into the database file, then re-run this script."
        )


def attach_cited_by_count(
    paper_df: pd.DataFrame,
    cache_path: Path = DEFAULT_CITED_CACHE,
) -> pd.DataFrame:
    """Map OpenAlex cited_by_count onto paper_df using the notebook's JSON cache."""
    paper_df = paper_df.copy()
    paper_df["doi_key"] = (
        paper_df["doi_norm"]
        .str.lower()
        .str.strip()
        .str.replace("https://doi.org/", "", regex=False)
    )

    if cache_path.exists():
        cited_map = json.loads(cache_path.read_text(encoding="utf-8"))
        paper_df["cited_by_count"] = paper_df["doi_key"].map(cited_map)
        found = paper_df["cited_by_count"].notna().sum()
        print(f"  Attached cited_by_count for {found:,} / {len(paper_df):,} papers.")
    else:
        print(
            f"  Warning: citation cache not found at {cache_path}; "
            "cited_by_count set to NaN."
        )
        paper_df["cited_by_count"] = np.nan

    return paper_df


def _sample_up_to_n(df: pd.DataFrame, n: int, group_col: str = "has_pr") -> pd.DataFrame:
    """Stratified sample without dropping the group column (pandas groupby.apply can)."""
    parts: list[pd.DataFrame] = []
    for _, group in df.groupby(group_col, sort=False):
        if len(group) <= n:
            parts.append(group)
        else:
            parts.append(group.sample(n=n, random_state=42))
    if not parts:
        return df.iloc[0:0].copy()
    return pd.concat(parts, ignore_index=True)


def load_paper_df(
    duckdb_path: Path = DEFAULT_DUCKDB,
    altmet_csv: Path = DEFAULT_ALTMET_CSV,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """Rebuild paper_df using the same logic as analysis.ipynb / 07_create_graphs.

    Opens the DuckDB file read-only and queries the views/tables already built
    by the matching pipeline. Does NOT call setup_views().
    """
    con = duckdb.connect(str(duckdb_path), read_only=True)
    assert_pipeline_objects(con)

    press_release_query = """
        SELECT * FROM (
            (SELECT pr_id, matched_doi FROM embedding_title_match)
            UNION
            (SELECT pr_id, matched_doi FROM pr_paper_matched WHERE is_matched = 1)
        )
    """
    press_release_data = con.sql(press_release_query).df()
    doi_list = con.sql("SELECT * FROM doi_list_norm").df()
    con.close()

    altmet_df = pd.read_csv(altmet_csv)
    altmet_df["doi_norm"] = altmet_df["doi"].str.lower().str.strip()
    doi_list["doi_norm"] = doi_list["doi"].str.lower().str.strip()
    altmet_df_joined = altmet_df.merge(
        doi_list[["doi_norm", "cited_by_count"]], on="doi_norm", how="inner"
    )

    press_release_data["matched_doi_norm"] = (
        press_release_data["matched_doi"].str.lower().str.strip()
    )
    pr_altmet_merged = altmet_df_joined.merge(
        press_release_data,
        right_on="matched_doi_norm",
        left_on="doi_norm",
        how="left",
        indicator="press_release_indicator",
    )

    paper_df = (
        pr_altmet_merged.sort_values(["doi_norm", "category"])
        .drop_duplicates("doi_norm", keep="first")
        .assign(
            has_pr=lambda d: d["press_release_indicator"].eq("both"),
            total_mentions=lambda d: d[MENTION_COLS].fillna(0).sum(axis=1),
            pub_year=lambda d: pd.to_datetime(d["publication_date"]).dt.year,
        )
    )

    usable_weights = {k: v for k, v in ATTENTION_WEIGHTS.items() if k in paper_df.columns}
    paper_df["attention_score"] = sum(
        paper_df.get(col, 0).fillna(0) * weight for col, weight in usable_weights.items()
    )

    if sample_size is not None and sample_size > 0:
        paper_df = _sample_up_to_n(paper_df, n=sample_size, group_col="has_pr")

    return paper_df


def slim_paper_df_for_dashboard(paper_df: pd.DataFrame) -> pd.DataFrame:
    """Keep only columns required by the Streamlit dashboard."""
    missing = [c for c in DASHBOARD_COLUMNS if c not in paper_df.columns]
    if missing:
        raise KeyError(f"paper_df missing required dashboard columns: {missing}")
    out = paper_df.loc[:, DASHBOARD_COLUMNS].copy()
    out["has_pr"] = out["has_pr"].astype(bool)
    if "pub_year" in out.columns:
        out["pub_year"] = pd.to_numeric(out["pub_year"], errors="coerce")
    return out


def category_combo_key(categories: list[str] | tuple[str, ...]) -> str:
    """Stable filesystem key for a category multiselect (sorted, joined)."""
    cats = sorted({str(c).strip() for c in categories if c})
    if not cats:
        return "none"
    return "__".join(cats)


def iter_category_combos(categories: list[str]) -> list[tuple[str, ...]]:
    """All non-empty subsets of categories (for precomputed dashboard caches)."""
    from itertools import combinations

    cats = sorted({str(c).strip() for c in categories if c})
    combos: list[tuple[str, ...]] = []
    for r in range(1, len(cats) + 1):
        combos.extend(combinations(cats, r))
    return combos


def coefficients_dir(out_dir: Path = DEFAULT_DASHBOARD_DIR) -> Path:
    return Path(out_dir) / "coefficients" / "by_category"


def overview_dir(out_dir: Path = DEFAULT_DASHBOARD_DIR) -> Path:
    return Path(out_dir) / "overview" / "by_category"


def coef_path_for_categories(
    categories: list[str] | tuple[str, ...],
    *,
    out_dir: Path = DEFAULT_DASHBOARD_DIR,
) -> Path:
    return coefficients_dir(out_dir) / f"{category_combo_key(categories)}.csv"


def overview_path_for_categories(
    categories: list[str] | tuple[str, ...],
    *,
    out_dir: Path = DEFAULT_DASHBOARD_DIR,
) -> Path:
    return overview_dir(out_dir) / f"{category_combo_key(categories)}.csv"


def filter_by_categories(
    paper_df: pd.DataFrame,
    categories: list[str] | tuple[str, ...],
) -> pd.DataFrame:
    cats = [c for c in categories if c]
    if not cats:
        return paper_df.iloc[0:0].copy()
    return paper_df.loc[paper_df["category"].isin(cats)].copy()


def save_dashboard_cache(
    paper_df: pd.DataFrame,
    *,
    out_dir: Path = DEFAULT_DASHBOARD_DIR,
    include_coefficients: bool = True,
) -> dict[str, Path]:
    """Write paper_df + per-category-combo overview/FE caches for Streamlit."""
    from datetime import datetime, timezone

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slim = slim_paper_df_for_dashboard(paper_df)
    paper_path = out_dir / "paper_df.parquet"
    slim.to_parquet(paper_path, index=False)

    paths: dict[str, Path] = {"paper_df": paper_path}

    all_categories = sorted(
        c for c in slim["category"].dropna().unique().tolist() if c
    )
    combos = iter_category_combos(all_categories)
    coef_dir = coefficients_dir(out_dir)
    ov_dir = overview_dir(out_dir)
    coef_dir.mkdir(parents=True, exist_ok=True)
    ov_dir.mkdir(parents=True, exist_ok=True)

    combo_meta: list[dict] = []
    print(f"  Writing caches for {len(combos)} category combinations …")
    for combo in combos:
        subset = impute_mention_zeros(filter_by_categories(slim, combo))
        key = category_combo_key(combo)
        ov_path = overview_path_for_categories(combo, out_dir=out_dir)
        overview_metric_stats(subset).to_csv(ov_path, index=False)
        paths[f"overview:{key}"] = ov_path

        coef_ok = False
        if include_coefficients:
            n_with = int(subset["has_pr"].sum())
            n_without = int((~subset["has_pr"]).sum())
            n_entities = int(subset["entity_name"].nunique())
            if len(subset) >= 50 and n_with >= 5 and n_without >= 5 and n_entities >= 2:
                try:
                    coef_df = fit_coefficient_forest(subset)
                    coef_path = coef_path_for_categories(combo, out_dir=out_dir)
                    coef_df.to_csv(coef_path, index=False)
                    paths[f"coefficients:{key}"] = coef_path
                    coef_ok = True
                    # Keep legacy path for the full (all categories) combo.
                    if list(combo) == all_categories:
                        legacy = out_dir / "coefficient_forest.csv"
                        coef_df.to_csv(legacy, index=False)
                        paths["coefficients"] = legacy
                except Exception as exc:  # noqa: BLE001
                    print(f"  Skipping FE cache for {key}: {exc}")

        combo_meta.append(
            {
                "categories": list(combo),
                "key": key,
                "n_papers": int(len(subset)),
                "n_with_pr": int(subset["has_pr"].sum()),
                "has_coefficients": coef_ok,
            }
        )
        print(
            f"  Cached combo [{key}]: {len(subset):,} papers"
            + (" + FE" if coef_ok else "")
        )

    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_papers": int(len(slim)),
        "n_with_pr": int(slim["has_pr"].sum()),
        "n_entities": int(slim["entity_name"].nunique()),
        "year_min": int(slim["pub_year"].min()) if slim["pub_year"].notna().any() else None,
        "year_max": int(slim["pub_year"].max()) if slim["pub_year"].notna().any() else None,
        "columns": list(slim.columns),
        "include_coefficients": include_coefficients,
        "imputed_zeros": True,
        "categories": all_categories,
        "category_combos": combo_meta,
    }
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    paths["meta"] = meta_path
    return paths


def load_paper_df_from_cache(
    parquet_path: Path = DEFAULT_PAPER_PARQUET,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """Load the prebuilt dashboard parquet (fast path for Streamlit)."""
    path = Path(parquet_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dashboard cache not found: {path}\n"
            "Build it once with:\n"
            "  python code/08_export_dashboard_data.py"
        )
    paper_df = pd.read_parquet(path)
    if "has_pr" in paper_df.columns:
        paper_df["has_pr"] = paper_df["has_pr"].astype(bool)
    if sample_size is not None and sample_size > 0:
        paper_df = _sample_up_to_n(paper_df, n=sample_size, group_col="has_pr")
    return paper_df


def load_cached_coefficients(
    coef_path: Path = DEFAULT_COEF_CSV,
) -> pd.DataFrame | None:
    """Load precomputed FE coefficients if present; else None."""
    path = Path(coef_path)
    if not path.exists():
        return None
    return pd.read_csv(path)


def load_cached_coefficients_for_categories(
    categories: list[str] | tuple[str, ...],
    *,
    out_dir: Path = DEFAULT_DASHBOARD_DIR,
) -> pd.DataFrame | None:
    """Load FE coefficients for a category multiselect combination."""
    return load_cached_coefficients(coef_path_for_categories(categories, out_dir=out_dir))


def load_cached_overview_for_categories(
    categories: list[str] | tuple[str, ...],
    *,
    out_dir: Path = DEFAULT_DASHBOARD_DIR,
) -> pd.DataFrame | None:
    """Load precomputed Section-1 overview stats for a category combination."""
    path = overview_path_for_categories(categories, out_dir=out_dir)
    if not path.exists():
        return None
    return pd.read_csv(path)


def impute_mention_zeros(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing mention / citation fields with 0 (does not change has_pr)."""
    out = df.copy()
    for col in MENTION_COLS + ["attention_score", "total_mentions"]:
        if col in out.columns:
            out[col] = out[col].fillna(0)
    usable_weights = {k: v for k, v in ATTENTION_WEIGHTS.items() if k in out.columns}
    out["attention_score"] = sum(
        out.get(col, 0).fillna(0) * weight for col, weight in usable_weights.items()
    )
    return out


def compute_group_stats(
    df: pd.DataFrame,
    group_col: str,
    metric: str,
    pr_col: str = "has_pr",
) -> tuple[list[str], list[float], list[float], list[float], list[float], list[int], list[int]]:
    """Return entity order, mean/SE, and N for with-PR and without-PR groups."""
    order = (
        df.groupby(group_col)
        .size()
        .sort_values(ascending=False)
        .index.tolist()
    )

    means_pr, errs_pr, means_no_pr, errs_no_pr = [], [], [], []
    n_pr, n_no_pr = [], []
    for entity in order:
        sub = df[df[group_col] == entity]
        with_pr = sub.loc[sub[pr_col], metric]
        without_pr = sub.loc[~sub[pr_col], metric]
        means_pr.append(float(with_pr.mean()) if len(with_pr) else float("nan"))
        errs_pr.append(float(with_pr.sem()) if len(with_pr) > 1 else 0.0)
        means_no_pr.append(float(without_pr.mean()) if len(without_pr) else float("nan"))
        errs_no_pr.append(float(without_pr.sem()) if len(without_pr) > 1 else 0.0)
        n_pr.append(int(len(with_pr)))
        n_no_pr.append(int(len(without_pr)))

    short_names = [short_entity_name(name) for name in order]
    return short_names, means_pr, errs_pr, means_no_pr, errs_no_pr, n_pr, n_no_pr


def overview_metric_stats(
    paper_df: pd.DataFrame,
) -> pd.DataFrame:
    """Mean ± SE and N by metric for with-PR vs without-PR (Section 1 table)."""
    rows = []
    for metric, label in zip(METRICS, METRIC_LABELS):
        for has_pr, group_label in ((True, "With PR"), (False, "Without PR")):
            group = paper_df.loc[paper_df["has_pr"] == has_pr, metric]
            rows.append(
                {
                    "metric": metric,
                    "metric_label": label,
                    "group": group_label,
                    "mean": float(group.mean()) if len(group) else float("nan"),
                    "se": float(group.sem()) if len(group) > 1 else 0.0,
                    "n": int(len(group)),
                }
            )
    return pd.DataFrame(rows)


def fit_coefficient_forest(paper_df: pd.DataFrame) -> pd.DataFrame:
    """OLS has_pr coefficients with entity FE (same spec as 07_create_graphs)."""
    import pyfixest as pf

    rows = []
    for metric, label in zip(METRICS, METRIC_LABELS):
        model = pf.feols(
            f"{metric} ~ has_pr | entity_name",
            data=paper_df,
            vcov={"CRV1": "entity_name"},
        )
        coef = float(model.coef().loc["has_pr"])
        se = float(model.se().loc["has_pr"])
        rows.append(
            {
                "metric": label,
                "coef": coef,
                "se": se,
                "ci_lo": coef - 1.96 * se,
                "ci_hi": coef + 1.96 * se,
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values("coef", ascending=True)
        .reset_index(drop=True)
    )
