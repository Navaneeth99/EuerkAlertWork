"""Build JSON payload that fills the HTML report template."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from utils.impact_analysis import short_entity_name

# Japanese universities in scope (all other in-scope entities → China).
JAPAN_INSTITUTIONS: frozenset[str] = frozenset(
    {
        "Nagoya University",
        "Hokkaido University",
        "University of Tokyo",
        "University of Kyoto",
        "Osaka Metropolitan University",
        "Osaka City University",
        "Osaka Prefecture University",
    }
)

OTHER_ENTITIES: frozenset[str] = frozenset(
    {
        "Institute of Physics of the Czech Academy of Sciences",
    }
)


def assign_region(entity_name: str) -> str:
    """Map entity_name to China, Japan, or Other for regional comparison."""
    name = str(entity_name).strip()
    if name in JAPAN_INSTITUTIONS:
        return "Japan"
    if name in OTHER_ENTITIES:
        return "Other"
    return "China"


def _load_altmet_source_count() -> int | None:
    """Altmetric deliverable row count for Figure 1.1 (lazy import for Streamlit reload)."""
    try:
        from utils.impact_analysis import load_altmet_source_count

        return load_altmet_source_count()
    except ImportError:
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        meta_path = root / "Processed" / "dashboard" / "meta.json"
        altmet_csv = root / "rawdata" / "AltMetData" / "aaas_deliverable_20260415.csv"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                n = meta.get("n_altmet_source")
                if n is not None:
                    return int(n)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        if altmet_csv.exists():
            with altmet_csv.open(encoding="utf-8", errors="replace") as f:
                next(f, None)
                n = sum(1 for _ in f)
            return n if n > 0 else None
        return None


REPORT_METRICS: list[tuple[str, str, str, str]] = [
    ("attention", "attention_score", "Attention Score", "Attention Score"),
    ("citations", "cited_by_count", "Citations", "Citations"),
    ("news", "news_mentions", "News Mentions", "News Mentions"),
    ("patent", "patent_mentions", "Patent Citations", "Patent Mentions"),
    ("policy", "policy_mentions", "Policy Mentions", "Policy Mentions"),
    ("x", "x_post_mentions", "X Mentions", "X Mentions"),
    ("facebook", "facebook_mentions", "Facebook Mentions", "Facebook Mentions"),
]

SCALE_KEYS = ("attention", "citations", "news", "x")


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _safe_mean(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if len(s) else 0.0


def _diff_se(with_vals: pd.Series, without_vals: pd.Series) -> float:
    """Standard error of mean(with) − mean(without) for raw comparison CIs."""
    w = pd.to_numeric(with_vals, errors="coerce").dropna()
    wo = pd.to_numeric(without_vals, errors="coerce").dropna()
    if len(w) < 2 or len(wo) < 2:
        return 0.0
    return float(np.sqrt(w.var(ddof=1) / len(w) + wo.var(ddof=1) / len(wo)))


def _coef_lookup(coef_df: pd.DataFrame | None) -> dict[str, tuple[float, float]]:
    """Map display/coef metric label → (coef, se)."""
    out: dict[str, tuple[float, float]] = {}
    if coef_df is None or coef_df.empty:
        return out
    for _, row in coef_df.iterrows():
        metric = str(row.get("metric", ""))
        try:
            out[metric] = (float(row["coef"]), float(row["se"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def build_region_comparison(paper_df: pd.DataFrame) -> dict[str, Any]:
    """Descriptive summary for China vs Japan regional comparison."""
    df = paper_df.copy()
    df["region"] = df["entity_name"].map(assign_region)
    china = df.loc[df["region"] == "China"]
    japan = df.loc[df["region"] == "Japan"]

    outcomes: list[dict[str, Any]] = []
    for key, col, label, _coef_label in REPORT_METRICS:
        if col not in df.columns:
            continue
        china_wo = _safe_mean(china.loc[~china["has_pr"], col]) if len(china) else 0.0
        china_w = _safe_mean(china.loc[china["has_pr"], col]) if len(china) else 0.0
        japan_wo = _safe_mean(japan.loc[~japan["has_pr"], col]) if len(japan) else 0.0
        japan_w = _safe_mean(japan.loc[japan["has_pr"], col]) if len(japan) else 0.0
        outcomes.append(
            {
                "key": key,
                "label": label,
                "china": {"wo": china_wo, "w": china_w},
                "japan": {"wo": japan_wo, "w": japan_w},
            }
        )

    n_china = int(len(china))
    n_japan = int(len(japan))
    n_china_with = int(china["has_pr"].sum()) if n_china else 0
    n_japan_with = int(japan["has_pr"].sum()) if n_japan else 0
    n_china_entities = int(china["entity_name"].nunique()) if n_china else 0
    n_japan_entities = int(japan["entity_name"].nunique()) if n_japan else 0

    return {
        "outcomes": outcomes,
        "meta": {
            "nChina": n_china,
            "nJapan": n_japan,
            "nChinaWithPr": n_china_with,
            "nJapanWithPr": n_japan_with,
            "nChinaEntities": n_china_entities,
            "nJapanEntities": n_japan_entities,
        },
    }


def build_report_payload(
    paper_df: pd.DataFrame,
    coef_df: pd.DataFrame | None = None,
    *,
    university_coef_df: pd.DataFrame | None = None,
    univ_jour_coef_df: pd.DataFrame | None = None,
    univ_jour_last_author_coef_df: pd.DataFrame | None = None,
    n_altmet_source: int | None = None,
    entities_per_panel: int = 8,
    max_entities: int | None = None,
) -> dict[str, Any]:
    """Compute METRICS / ENTITIES / scale / header fields for the report template.

    Figure 3.2 chips:
      raw                  — mean(with PR) − mean(without PR) on full sample
      university           — y ~ has_pr | fe_university on all institution papers
      univ_jour            — y ~ has_pr | entity_name on institution + journal papers
      univ_jour_last_author — y ~ has_pr | entity_name + last_author_id (inst + journal)
    """
    df = paper_df.copy()
    if "has_pr" in df.columns:
        df["has_pr"] = df["has_pr"].astype(bool)

    n_total = int(len(df))
    n_with = int(df["has_pr"].sum()) if n_total else 0
    n_without = n_total - n_with
    pct = (100.0 * n_with / n_total) if n_total else 0.0

    df["region"] = df["entity_name"].map(assign_region)
    n_china = int((df["region"] == "China").sum())
    n_japan = int((df["region"] == "Japan").sum())
    n_china_with = int(df.loc[df["region"] == "China", "has_pr"].sum())
    n_japan_with = int(df.loc[df["region"] == "Japan", "has_pr"].sum())

    year_min = year_max = None
    if "pub_year" in df.columns and df["pub_year"].notna().any():
        year_min = int(df["pub_year"].min())
        year_max = int(df["pub_year"].max())
    years = (
        f"{year_min}–{year_max}"
        if year_min is not None and year_max is not None
        else "all years"
    )

    with_pr = df.loc[df["has_pr"]]
    without_pr = df.loc[~df["has_pr"]]
    inst_df = df.loc[df["category"] == "institution"]
    uj_df = df.loc[df["category"].isin(["institution", "journal"])]

    coef_map = _coef_lookup(coef_df)
    univ_map = _coef_lookup(university_coef_df)
    uj_map = _coef_lookup(univ_jour_coef_df)
    uj_la_map = _coef_lookup(univ_jour_last_author_coef_df)
    has_univ_jour = bool(uj_map)
    has_univ_jour_last_author = bool(uj_la_map)

    metrics: list[dict[str, Any]] = []
    for key, col, label, coef_label in REPORT_METRICS:
        wo = _safe_mean(without_pr[col]) if col in without_pr.columns else 0.0
        w = _safe_mean(with_pr[col]) if col in with_pr.columns else 0.0
        raw = w - wo
        raw_se = (
            _diff_se(with_pr[col], without_pr[col])
            if col in with_pr.columns and col in without_pr.columns
            else 0.0
        )
        fe, se = coef_map.get(coef_label, (raw, 0.0))
        univ, univ_se = univ_map.get(coef_label, (fe, se))
        uj, uj_se = uj_map.get(coef_label, (fe, se))
        uj_la, uj_la_se = uj_la_map.get(coef_label, (uj, uj_se))

        inst_wo = (
            _safe_mean(inst_df.loc[~inst_df["has_pr"], col])
            if col in inst_df.columns and len(inst_df)
            else wo
        )
        inst_w = (
            _safe_mean(inst_df.loc[inst_df["has_pr"], col])
            if col in inst_df.columns and len(inst_df)
            else w
        )
        uj_wo = (
            _safe_mean(uj_df.loc[~uj_df["has_pr"], col])
            if col in uj_df.columns and len(uj_df)
            else wo
        )
        uj_w = (
            _safe_mean(uj_df.loc[uj_df["has_pr"], col])
            if col in uj_df.columns and len(uj_df)
            else w
        )
        metrics.append(
            {
                "key": key,
                "label": label,
                "wo": wo,
                "w": w,
                "woInst": inst_wo,
                "wInst": inst_w,
                "woUniJour": uj_wo,
                "wUniJour": uj_w,
                "raw": raw,
                "rawSe": raw_se,
                "univ": univ,
                "univSe": univ_se,
                "fe": fe,
                "se": se,
                "univJour": uj,
                "univJourSe": uj_se,
                "univJourLastAuthor": uj_la,
                "univJourLastAuthorSe": uj_la_se,
            }
        )

    scale_data: list[dict[str, Any]] = []
    for key, col, label, _coef_label in REPORT_METRICS:
        if key not in SCALE_KEYS or col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").fillna(0)
        scale_data.append(
            {
                "label": label,
                "min": float(s.min()) if len(s) else 0.0,
                "med": float(s.median()) if len(s) else 0.0,
                "mean": float(s.mean()) if len(s) else 0.0,
                "max": float(s.max()) if len(s) else 0.0,
            }
        )

    counts = (
        df.groupby(["entity_name", "category"], dropna=False)
        .size()
        .reset_index(name="papers")
        .sort_values("papers", ascending=False)
    )
    if max_entities is not None:
        counts = counts.head(int(max_entities))
    entities: list[dict[str, Any]] = []
    entity_means: dict[str, dict[str, dict[str, float]]] = {}
    for _, row in counts.iterrows():
        name = short_entity_name(str(row["entity_name"]))
        full = str(row["entity_name"])
        cat = str(row["category"]) if pd.notna(row["category"]) else "entity"
        sub = df.loc[df["entity_name"] == full]
        with_n = int(sub["has_pr"].sum())
        entities.append(
            {
                "name": name,
                "full_name": full,
                "type": cat,
                "papers": int(row["papers"]),
                "withPr": with_n,
            }
        )
        means: dict[str, dict[str, float]] = {}
        for mkey, col, _label, _coef_label in REPORT_METRICS:
            if col not in sub.columns:
                means[mkey] = {"w": 0.0, "wo": 0.0}
                continue
            means[mkey] = {
                "w": _safe_mean(sub.loc[sub["has_pr"], col]),
                "wo": _safe_mean(sub.loc[~sub["has_pr"], col]),
            }
        entity_means[name] = means

    if n_altmet_source is None:
        n_altmet_source = _load_altmet_source_count()

    n_entities = (
        int(df["entity_name"].nunique())
        if "entity_name" in df.columns and n_total
        else 0
    )

    header = {
        "HDR_N_PAPERS": _fmt_int(n_total),
        "HDR_N_WITH": _fmt_int(n_with),
        "HDR_N_WITHOUT": _fmt_int(n_without),
        "HDR_PCT": f"{pct:.1f}%",
        "HDR_YEARS": years,
        "HDR_N_ENTITIES": _fmt_int(n_entities),
        "HDR_N_ALTMET": _fmt_int(n_altmet_source) if n_altmet_source else "—",
        "HDR_N_CHINA": _fmt_int(n_china),
        "HDR_N_JAPAN": _fmt_int(n_japan),
        "HDR_N_CHINA_WITH": _fmt_int(n_china_with),
        "HDR_N_JAPAN_WITH": _fmt_int(n_japan_with),
    }

    region_comparison = build_region_comparison(df)

    return {
        "metrics": metrics,
        "entities": entities,
        "entityMeans": entity_means,
        "scaleData": scale_data,
        "entitiesPerPanel": entities_per_panel,
        "defaultSpec": "univ_jour",
        "showTakeaways": True,
        "header": header,
        "specNotes": {
            "raw": "No controls — naive mean(with PR) − mean(without PR) on the full sample.",
            "university": (
                "University fixed effects on all institution papers "
                "(y ~ has_pr | fe_university)."
            ),
            "univ_jour": (
                "Entity FE on institution + journal papers (full sample): "
                "y ~ has_pr | entity_name."
                if has_univ_jour
                else (
                    "University + journal FE cache not available — rebuild dashboard "
                    "cache (08_export_dashboard_data.py)."
                )
            ),
            "univ_jour_last_author": (
                "Entity + last-author FE on institution + journal papers (full sample): "
                "y ~ has_pr | entity_name + last_author_id."
                if has_univ_jour_last_author
                else (
                    "University + journal + last-author FE cache not available — "
                    "rebuild dashboard cache."
                )
            ),
        },
        "n_total": n_total,
        "n_with": n_with,
        "n_without": n_without,
        "n_china": n_china,
        "n_japan": n_japan,
        "n_china_with_pr": n_china_with,
        "n_japan_with_pr": n_japan_with,
        "n_institution": int(len(inst_df)),
        "n_univ_jour": int(len(uj_df)),
        "has_univ_jour_fe": has_univ_jour,
        "has_univ_jour_last_author_fe": has_univ_jour_last_author,
        "regionComparison": region_comparison,
    }


def render_report_html(
    template_html: str,
    dclogic_js: str,
    payload: dict[str, Any],
) -> str:
    """Inject DCLogic runtime, JSON payload, and header tokens into the template."""
    import json

    html = template_html.replace("/*__DCLOGIC__*/", dclogic_js)
    data_json = json.dumps(payload, allow_nan=False)
    html = html.replace("/*__REPORT_DATA__*/null", data_json)
    for key, value in payload.get("header", {}).items():
        html = html.replace(f"__{key}__", str(value))
    return html
