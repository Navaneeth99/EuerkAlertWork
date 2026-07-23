"""Build JSON payload that fills the HTML report template."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from utils.impact_analysis import pub_year_range, short_entity_name


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

# Template metric keys → paper_df columns (order matches the report Component).
# coef_label matches the `metric` column written by fit_coefficient_forest.
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


def build_report_payload(
    paper_df: pd.DataFrame,
    coef_df: pd.DataFrame | None = None,
    *,
    university_coef_df: pd.DataFrame | None = None,
    journal_coef_df: pd.DataFrame | None = None,
    field_coef_df: pd.DataFrame | None = None,
    last_author_coef_df: pd.DataFrame | None = None,
    n_altmet_source: int | None = None,
    entities_per_panel: int = 8,
    max_entities: int | None = None,
) -> dict[str, Any]:
    """Compute METRICS / ENTITIES / scale / header fields for the report template.

    Figure 3.2 chips map to distinct estimates:
      raw         — mean(with PR) − mean(without PR); shown as baseline reference on FE specs
      university  — entity FE on institution-category papers only
      journal     — entity FE on journal-category papers only
      field       — field FE (OpenAlex primary_topic.field): y ~ has_pr | field_id
      fe          — entity FE on the full filtered sample (universities + journals)
      last_author — last-author FE (falls back to entity FE if unavailable)

    entities_per_panel limits bars in Fig 4.1 small multiples.
    max_entities limits the Fig 3.3 dropdown (None = all entities in the sample).
    """
    df = paper_df.copy()
    if "has_pr" in df.columns:
        df["has_pr"] = df["has_pr"].astype(bool)

    n_total = int(len(df))
    n_with = int(df["has_pr"].sum()) if n_total else 0
    n_without = n_total - n_with
    pct = (100.0 * n_with / n_total) if n_total else 0.0

    year_min, year_max = pub_year_range(df["pub_year"]) if "pub_year" in df.columns else (None, None)
    years = (
        f"{year_min}–{year_max}"
        if year_min is not None and year_max is not None
        else "all years"
    )

    with_pr = df.loc[df["has_pr"]]
    without_pr = df.loc[~df["has_pr"]]
    inst_df = df.loc[df["category"] == "institution"]
    jour_df = df.loc[df["category"] == "journal"]
    coef_map = _coef_lookup(coef_df)
    univ_map = _coef_lookup(university_coef_df)
    jour_map = _coef_lookup(journal_coef_df)
    field_map = _coef_lookup(field_coef_df)
    la_map = _coef_lookup(last_author_coef_df)
    has_last_author = bool(la_map)
    has_field = bool(field_map)

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
        jour, jour_se = jour_map.get(coef_label, (fe, se))
        fld, fld_se = field_map.get(coef_label, (fe, se))
        la, la_se = la_map.get(coef_label, (fe, se))
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
        jour_wo = (
            _safe_mean(jour_df.loc[~jour_df["has_pr"], col])
            if col in jour_df.columns and len(jour_df)
            else wo
        )
        jour_w = (
            _safe_mean(jour_df.loc[jour_df["has_pr"], col])
            if col in jour_df.columns and len(jour_df)
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
                "woJour": jour_wo,
                "wJour": jour_w,
                "raw": raw,
                "rawSe": raw_se,
                "univ": univ,
                "univSe": univ_se,
                "jour": jour,
                "jourSe": jour_se,
                "field": fld,
                "fieldSe": fld_se,
                "fe": fe,
                "lastAuthor": la,
                "se": se,
                "lastAuthorSe": la_se,
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

    # All entities for Fig 3.3 dropdown (sorted by paper count). Optionally capped.
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
        for key, col, _label, _coef_label in REPORT_METRICS:
            if col not in sub.columns:
                means[key] = {"w": 0.0, "wo": 0.0}
                continue
            means[key] = {
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
    }

    la_note = (
        "Within last-author comparison: y ~ has_pr | last_author_id."
        if has_last_author
        else (
            "Last-author FE cache not available yet — showing entity FE. "
            "Rebuild the dashboard cache after last-author enrichment."
        )
    )
    field_note = (
        "Within OpenAlex field comparison: y ~ has_pr | field_id "
        "(primary_topic.field.display_name)."
        if has_field
        else (
            "Field FE cache not available yet — rebuild after re-fetching DOIs with "
            "primary_topic and re-running 03_extract_dois.py + 08_export_dashboard_data.py."
        )
    )

    return {
        "metrics": metrics,
        "entities": entities,
        "entityMeans": entity_means,
        "scaleData": scale_data,
        "entitiesPerPanel": entities_per_panel,
        "defaultSpec": "fe",
        "showTakeaways": True,
        "header": header,
        "specNotes": {
            "raw": "No controls — naive mean(with PR) − mean(without PR).",
            "university": (
                "University fixed effects on institution papers only "
                "(y ~ has_pr | entity_name, category = institution)."
            ),
            "journal": (
                "Journal fixed effects on journal papers only "
                "(y ~ has_pr | entity_name, category = journal)."
            ),
            "field": field_note,
            "fe": (
                "Entity fixed effects across universities and journals "
                "(y ~ has_pr | entity_name)."
            ),
            "last_author": la_note,
        },
        "n_total": n_total,
        "n_with": n_with,
        "n_without": n_without,
        "has_last_author_fe": has_last_author,
        "has_field_fe": has_field,
    }


def render_report_html(
    template_html: str,
    dclogic_js: str,
    payload: dict[str, Any],
) -> str:
    """Inject DCLogic runtime, JSON payload, and header tokens into the template."""
    import json

    html = template_html.replace("/*__DCLOGIC__*/", dclogic_js)
    # Keep JSON safe inside a <script> assignment.
    data_json = json.dumps(payload, allow_nan=False)
    html = html.replace("/*__REPORT_DATA__*/null", data_json)
    for key, value in payload.get("header", {}).items():
        html = html.replace(f"__{key}__", str(value))
    return html
