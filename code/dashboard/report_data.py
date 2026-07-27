"""Build JSON payload that fills the HTML report template."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from utils.impact_analysis import short_entity_name


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


_LINEAR_HIST_CAP = 500
_LINEAR_HIST_BIN_WIDTH = 50
_LOG_HIST_CAP = 2.5
_LOG_HIST_BIN_WIDTH = 0.25


def _linear_bin_citation_range(lo: float, hi: float, *, is_last: bool) -> str:
    lo_i = int(lo)
    if is_last:
        return f"{lo_i}+ cites"
    return f"{lo_i}–{int(hi)} cites"


def _fmt_cite_bound(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _fmt_log_bound(x: float) -> str:
    text = f"{x:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _log_bin_labels(
    lo: float, hi: float, *, is_last: bool = False
) -> tuple[str, str]:
    """Log10(c+1) bucket label and corresponding citation range."""
    if is_last:
        lo_c = max(0, int(np.floor(10**lo - 1)))
        return f"{_fmt_log_bound(lo)}+", f"{_fmt_cite_bound(lo_c)}+ cites"

    log_range = f"{_fmt_log_bound(lo)}–{_fmt_log_bound(hi)}"
    if lo == 0.0 and hi == _LOG_HIST_BIN_WIDTH:
        return log_range, "0 cites"
    if lo == _LOG_HIST_BIN_WIDTH and hi == 2 * _LOG_HIST_BIN_WIDTH:
        return log_range, "1–2 cites"

    lo_c = max(0, int(np.floor(10**lo - 1)))
    hi_c = max(lo_c, int(np.ceil(10**hi - 1)) - 1)
    if hi_c <= lo_c:
        hi_c = lo_c + 1
    cite_range = f"{_fmt_cite_bound(lo_c)}–{_fmt_cite_bound(hi_c)} cites"

    return log_range, cite_range


def build_citation_histogram(df: pd.DataFrame) -> dict[str, Any]:
    """Histogram bins: equal-width on linear citations vs equal-width on log10(citations+1)."""
    if "cited_by_count" not in df.columns or df.empty:
        return {"linear": [], "log": [], "median": 0.0, "mean": 0.0, "max": 0.0}

    s = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).clip(lower=0)
    n = len(s)
    max_cit = float(s.max()) if n else 0.0
    linear_cap = float(_LINEAR_HIST_CAP)
    log_vals = np.log10(s + 1.0)
    log_cap = float(_LOG_HIST_CAP)
    log_skew = float(pd.Series(log_vals).skew()) if n else 0.0
    raw_skew = float(s.skew()) if n else 0.0

    linear_edges = list(range(0, _LINEAR_HIST_CAP + 1, _LINEAR_HIST_BIN_WIDTH))
    linear: list[dict[str, Any]] = []
    for i in range(len(linear_edges) - 1):
        lo_e, hi_e = float(linear_edges[i]), float(linear_edges[i + 1])
        is_last = i == len(linear_edges) - 2
        if not is_last:
            cnt = int(((s >= lo_e) & (s < hi_e)).sum())
        else:
            cnt = int((s >= lo_e).sum())
        linear.append(
            {
                "range": _linear_bin_citation_range(lo_e, hi_e, is_last=is_last),
                "count": cnt,
                "pct": (100.0 * cnt / n) if n else 0.0,
                "lo": lo_e,
                "hi": hi_e,
            }
        )

    log_step_count = int(_LOG_HIST_CAP / _LOG_HIST_BIN_WIDTH)
    log_edges = [i * _LOG_HIST_BIN_WIDTH for i in range(log_step_count + 1)]
    log: list[dict[str, Any]] = []
    for i in range(len(log_edges) - 1):
        lo_e, hi_e = float(log_edges[i]), float(log_edges[i + 1])
        cnt = int(((log_vals >= lo_e) & (log_vals < hi_e)).sum())
        log_range, cite_range = _log_bin_labels(lo_e, hi_e, is_last=False)
        log.append(
            {
                "range": f"{log_range} · {cite_range}",
                "logRange": log_range,
                "citeRange": cite_range,
                "count": cnt,
                "pct": (100.0 * cnt / n) if n else 0.0,
                "lo": lo_e,
                "hi": hi_e,
            }
        )

    tail_lo = float(log_edges[-1])
    tail_cnt = int((log_vals >= tail_lo).sum())
    tail_log, tail_cite = _log_bin_labels(tail_lo, tail_lo, is_last=True)
    log.append(
        {
            "range": f"{tail_log} · {tail_cite}",
            "logRange": tail_log,
            "citeRange": tail_cite,
            "count": tail_cnt,
            "pct": (100.0 * tail_cnt / n) if n else 0.0,
            "lo": tail_lo,
            "hi": None,
        }
    )

    return {
        "linear": linear,
        "log": log,
        "median": float(s.median()) if len(s) else 0.0,
        "mean": float(s.mean()) if len(s) else 0.0,
        "max": max_cit,
        "linearCap": linear_cap,
        "logCap": log_cap,
        "rawSkew": raw_skew,
        "logSkew": log_skew,
    }


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
    univ_jour_coef_df: pd.DataFrame | None = None,
    univ_jour_field_coef_df: pd.DataFrame | None = None,
    univ_jour_last_author_coef_df: pd.DataFrame | None = None,
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
      fe          — entity FE on the full filtered sample (Figure 3.1 only)
      last_author — last-author FE: y ~ has_pr | last_author_id
      univ_jour   — entity FE on institution + journal papers
      univ_jour_field — y ~ has_pr | entity_name + field_id (institution + journal)
      univ_jour_last_author — y ~ has_pr | entity_name + last_author_id (institution + journal)

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
    jour_df = df.loc[df["category"] == "journal"]
    uj_df = df.loc[df["category"].isin(["institution", "journal"])]
    coef_map = _coef_lookup(coef_df)
    univ_map = _coef_lookup(university_coef_df)
    jour_map = _coef_lookup(journal_coef_df)
    field_map = _coef_lookup(field_coef_df)
    la_map = _coef_lookup(last_author_coef_df)
    uj_map = _coef_lookup(univ_jour_coef_df)
    uj_field_map = _coef_lookup(univ_jour_field_coef_df)
    uj_la_map = _coef_lookup(univ_jour_last_author_coef_df)
    has_last_author = bool(la_map)
    has_field = bool(field_map)
    has_univ_jour = bool(uj_map)
    has_univ_jour_field = bool(uj_field_map)
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
        jour, jour_se = jour_map.get(coef_label, (fe, se))
        fld, fld_se = field_map.get(coef_label, (fe, se))
        la, la_se = la_map.get(coef_label, (fe, se))
        uj, uj_se = uj_map.get(coef_label, (fe, se))
        uj_fld, uj_fld_se = uj_field_map.get(coef_label, (uj, uj_se))
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
                "woJour": jour_wo,
                "wJour": jour_w,
                "woUniJour": uj_wo,
                "wUniJour": uj_w,
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
                "univJour": uj,
                "univJourSe": uj_se,
                "univJourField": uj_fld,
                "univJourFieldSe": uj_fld_se,
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

    uj_note = (
        "Entity FE on institution + journal papers: y ~ has_pr | entity_name."
        if has_univ_jour
        else (
            "University + journal FE cache not available — rebuild dashboard cache "
            "after export (08_export_dashboard_data.py)."
        )
    )
    uj_field_note = (
        "Two-way FE on institution + journal papers: "
        "y ~ has_pr | entity_name + field_id."
        if has_univ_jour_field
        else (
            "University + journal + field FE cache not available — rebuild dashboard "
            "cache after re-export."
        )
    )
    uj_la_note = (
        "Two-way FE on institution + journal papers: "
        "y ~ has_pr | entity_name + last_author_id."
        if has_univ_jour_last_author
        else (
            "University + journal + last-author FE cache not available — rebuild "
            "dashboard cache after re-export."
        )
    )

    citation_hist = build_citation_histogram(df)

    return {
        "metrics": metrics,
        "entities": entities,
        "entityMeans": entity_means,
        "scaleData": scale_data,
        "citationHist": citation_hist,
        "entitiesPerPanel": entities_per_panel,
        "defaultSpec": "univ_jour",
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
            "last_author": la_note,
            "univ_jour": uj_note,
            "univ_jour_field": uj_field_note,
            "univ_jour_last_author": uj_la_note,
        },
        "n_total": n_total,
        "n_with": n_with,
        "n_without": n_without,
        "has_last_author_fe": has_last_author,
        "has_field_fe": has_field,
        "has_univ_jour_fe": has_univ_jour,
        "has_univ_jour_field_fe": has_univ_jour_field,
        "has_univ_jour_last_author_fe": has_univ_jour_last_author,
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
