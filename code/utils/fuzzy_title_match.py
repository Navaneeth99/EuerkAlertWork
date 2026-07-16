"""Fuzzy title match: PR Article Title <-> DOI title via rapidfuzz.

Scoped to the same entity_name (from scope_name_text_search) and optional
publication-date window. Runs after exact title, before embedding.

Usage (via matching pipeline):
  python code/06_matching_pipeline.py
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

MIN_SCORE = 85.0  # rapidfuzz token_set_ratio (0–100)
MAX_DAYS = 348

# Align scope entity_name with DOIList when names diverge.
ENTITY_NAME_ALIASES_SQL = """
CASE trim(sns.canonical_name)
  WHEN 'Chinese Academy of Sciences' THEN 'Chinese Academy of Sciences Headquarters'
  ELSE sns.canonical_name
END
"""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _date_ok(pub_date, paper_date, max_days):
    if pub_date is None or paper_date is None or max_days is None:
        return True
    return abs((pd.Timestamp(pub_date) - pd.Timestamp(paper_date)).days) <= max_days


def _unmatched_prs(con):
    """PRs not DOI/exact-title matched, with scope entity + Article Title."""
    con.execute(f"""
        CREATE OR REPLACE TABLE unmatched_pr_fuzzy AS
        SELECT
            CAST(pr."PR ID" AS VARCHAR) AS pr_id,
            {ENTITY_NAME_ALIASES_SQL} AS entity_name,
            pr.pub_date,
            trim(pr."Article Title") AS pr_title
        FROM pr_base pr
        JOIN scope_name_text_search sns ON pr."PR ID" = sns."PR ID"
        WHERE pr."PR ID" NOT IN (SELECT pr_id FROM doi_match)
          AND pr."PR ID" NOT IN (SELECT pr_id FROM title_match)
          AND pr."Article Title" IS NOT NULL
          AND trim(pr."Article Title") != ''
    """)


def _scoped_dois(con):
    return con.execute("""
        SELECT d.doi, d.entity_name, d.title, d.publication_date AS paper_date
        FROM doi_list_norm d
        WHERE d.entity_name IN (SELECT DISTINCT entity_name FROM unmatched_pr_fuzzy)
          AND d.title IS NOT NULL AND trim(d.title) != ''
    """).df()


def run_fuzzy_title_match(con, min_score: float = MIN_SCORE, max_days: int = MAX_DAYS) -> int:
    """Match unmatched scoped PRs to best same-entity DOI title via rapidfuzz."""
    from rapidfuzz import fuzz, process

    _unmatched_prs(con)
    pr_df = con.execute("SELECT * FROM unmatched_pr_fuzzy").df()
    doi_df = _scoped_dois(con)

    if pr_df.empty or doi_df.empty:
        con.execute("""
            CREATE OR REPLACE TABLE fuzzy_title_match (
                pr_id VARCHAR, matched_doi VARCHAR, entity_name VARCHAR,
                paper_title VARCHAR, paper_date DATE, pub_date DATE,
                fuzzy_score DOUBLE, pr_title VARCHAR
            )
        """)
        return 0

    pr_df["pr_title_clean"] = pr_df["pr_title"].map(_clean)
    doi_df["title_clean"] = doi_df["title"].map(_clean)

    entities = list(pr_df.groupby("entity_name"))
    n_entities = len(entities)
    print(
        f"Fuzzy title match: {n_entities:,} entities, "
        f"{len(pr_df):,} PRs, {len(doi_df):,} DOIs "
        f"(min_score={min_score}, max_days={max_days})",
        flush=True,
    )

    matches = []
    t0 = time.perf_counter()
    for idx, (entity, pr_sub) in enumerate(entities, start=1):
        doi_sub = doi_df[doi_df.entity_name == entity].reset_index(drop=True)
        if pr_sub.empty or doi_sub.empty:
            print(
                f"[{idx}/{n_entities}] {entity}: skip "
                f"(prs={len(pr_sub)}, dois={len(doi_sub)})",
                flush=True,
            )
            continue

        entity_t0 = time.perf_counter()
        titles = doi_sub["title_clean"].tolist()
        entity_matches = 0
        entity_scored = 0
        entity_max = None
        entity_min = None

        for pr_row in pr_sub.itertuples():
            query = pr_row.pr_title_clean
            if not query:
                continue
            valid_idx = [
                j
                for j, paper in enumerate(doi_sub.itertuples())
                if _date_ok(pr_row.pub_date, paper.paper_date, max_days)
            ]
            if not valid_idx:
                continue

            cand_titles = [titles[j] for j in valid_idx]
            hit = process.extractOne(
                query,
                cand_titles,
                scorer=fuzz.token_set_ratio,
                score_cutoff=min_score,
            )
            entity_scored += 1
            if hit is None:
                continue

            score, local_i = float(hit[1]), hit[2]
            j = valid_idx[local_i]
            if entity_max is None or score > entity_max:
                entity_max = score
            if entity_min is None or score < entity_min:
                entity_min = score

            paper = doi_sub.iloc[j]
            matches.append(
                {
                    "pr_id": str(pr_row.pr_id),
                    "matched_doi": paper.doi,
                    "entity_name": entity,
                    "paper_title": paper.title,
                    "paper_date": paper.paper_date,
                    "pub_date": pr_row.pub_date,
                    "fuzzy_score": score,
                    "pr_title": pr_row.pr_title,
                }
            )
            entity_matches += 1

        elapsed = time.perf_counter() - entity_t0
        max_s = f"{entity_max:.1f}" if entity_max is not None else "n/a"
        min_s = f"{entity_min:.1f}" if entity_min is not None else "n/a"
        print(
            f"[{idx}/{n_entities}] {entity}: "
            f"prs={len(pr_sub):,}, dois={len(doi_sub):,}, "
            f"matched={entity_matches:,}/{entity_scored:,} scored, "
            f"score=[{min_s},{max_s}], {elapsed:.1f}s",
            flush=True,
        )

    total_elapsed = time.perf_counter() - t0
    print(
        f"Fuzzy title match done: {len(matches):,} rows in {total_elapsed:.1f}s",
        flush=True,
    )

    out = pd.DataFrame(matches)
    con.register("_fuzzy", out)
    con.execute("CREATE OR REPLACE TABLE fuzzy_title_match AS SELECT * FROM _fuzzy")
    con.unregister("_fuzzy")
    return len(out)
