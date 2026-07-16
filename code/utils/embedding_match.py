import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

EMBED_DIR = Path(__file__).resolve().parent.parent.parent / "Processed" / "embeddings"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SIM = 0.7  # optional quality cutoff; default matching keeps every PR's top DOI

# Align scope entity_name with DOIList when names diverge.
ENTITY_NAME_ALIASES_SQL = """
CASE trim(s.entity_name)
  WHEN 'Chinese Academy of Sciences' THEN 'Chinese Academy of Sciences Headquarters'
  ELSE s.entity_name
END
"""

PR_TEXT = """coalesce(
    nullif(trim(pr."Article Title"), ''),
    nullif(trim(pr.Headline), ''),
    nullif(trim(left(pr."Summary", 500)), '')
)"""


def _clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _encode(model, texts, batch_size=256):
    return model.encode(
        [_clean(t) for t in texts],
        batch_size=batch_size,
        show_progress_bar=len(texts) > 500,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )


def _unmatched_prs(con):
    con.execute(f"""
        CREATE OR REPLACE TABLE unmatched_pr_scope AS
        SELECT
            s.pr_id,
            {ENTITY_NAME_ALIASES_SQL} AS entity_name,
            s.pub_date,
            {PR_TEXT} AS pr_text
        FROM pr_paper_matched s
        JOIN pr_base pr ON s.pr_id = pr."PR ID"
        WHERE s.is_matched = 0
          AND s.entity_name IS NOT NULL
          AND {PR_TEXT} IS NOT NULL
    """)


def _scoped_dois(con):
    return con.execute("""
        SELECT d.doi, d.entity_name, d.title, d.publication_date AS paper_date
        FROM doi_list_norm d
        WHERE d.entity_name IN (SELECT DISTINCT entity_name FROM unmatched_pr_scope)
          AND d.title IS NOT NULL AND trim(d.title) != ''
    """).df()


def _date_ok(pub_date, paper_date, max_days):
    if pub_date is None or paper_date is None or max_days is None:
        return True
    return abs((pd.Timestamp(pub_date) - pd.Timestamp(paper_date)).days) <= max_days


def _emb_matrix(col):
    return np.vstack([np.asarray(x, dtype=np.float32) for x in col])


def _attach_embeddings(df, id_col, text_col, path, model, rebuild):
    if not rebuild and path.exists():
        cached = pd.read_parquet(path)
        if "embedding" in cached.columns:
            df = df.drop(columns=["embedding"], errors="ignore")
            df = df.merge(cached[[id_col, "embedding"]], on=id_col, how="left")
    if "embedding" not in df.columns:
        df["embedding"] = pd.Series([None] * len(df), dtype=object)
    missing = df["embedding"].isna() | df["embedding"].isnull()
    if missing.any():
        emb = _encode(model, df.loc[missing, text_col].tolist())
        idx = df.index[missing]
        df.loc[idx, "embedding"] = pd.Series(list(emb), index=idx, dtype=object)
    df[[id_col, "embedding"]].drop_duplicates(id_col).to_parquet(path, index=False)
    return df


def run_embedding_match(con, min_sim=None, max_days=348, rebuild=False):
    """Match each unmatched scoped PR to its best same-entity DOI title.

    By default keeps the top DOI for every PR with a date-valid candidate
    (no similarity floor). Pass ``min_sim`` (e.g. 0.7) to drop weaker scores.
    """
    from sentence_transformers import SentenceTransformer

    _unmatched_prs(con)

    pr_df = con.execute("SELECT * FROM unmatched_pr_scope").df()
    doi_df = _scoped_dois(con)
    if pr_df.empty or doi_df.empty:
        con.execute("""
            CREATE OR REPLACE TABLE embedding_title_match (
                pr_id BIGINT, matched_doi VARCHAR, entity_name VARCHAR,
                paper_title VARCHAR, paper_date DATE, pub_date DATE,
                embedding_sim DOUBLE, pr_text VARCHAR
            )
        """)
        return 0

    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    doi_path = EMBED_DIR / "doi_embeddings.parquet"
    pr_path = EMBED_DIR / "pr_embeddings.parquet"
    model = SentenceTransformer(MODEL)

    doi_df = _attach_embeddings(doi_df, "doi", "title", doi_path, model, rebuild)
    pr_df = _attach_embeddings(pr_df, "pr_id", "pr_text", pr_path, model, rebuild)

    entities = list(pr_df.groupby("entity_name"))
    n_entities = len(entities)
    thresh_s = f"min_sim={min_sim}" if min_sim is not None else "top-1 (no min_sim)"
    print(
        f"Embedding similarity match: {n_entities:,} entities, "
        f"{len(pr_df):,} PRs, {len(doi_df):,} DOIs ({thresh_s})",
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
        pr_emb = _emb_matrix(pr_sub["embedding"])
        doi_emb = _emb_matrix(doi_sub["embedding"])
        sim = pr_emb @ doi_emb.T

        entity_matches = 0
        entity_scored = 0
        entity_ge_min = 0
        entity_max_sim = None
        entity_min_sim_seen = None
        for i, pr_row in enumerate(pr_sub.itertuples()):
            valid = [
                j for j, paper in enumerate(doi_sub.itertuples())
                if _date_ok(pr_row.pub_date, paper.paper_date, max_days)
            ]
            if not valid:
                continue
            j = valid[int(np.argmax(sim[i, valid]))]
            score = float(sim[i, j])
            entity_scored += 1
            if entity_max_sim is None or score > entity_max_sim:
                entity_max_sim = score
            if entity_min_sim_seen is None or score < entity_min_sim_seen:
                entity_min_sim_seen = score
            if score >= MIN_SIM:
                entity_ge_min += 1
            if min_sim is not None and score < min_sim:
                continue
            paper = doi_sub.iloc[j]
            matches.append({
                "pr_id": int(pr_row.pr_id),
                "matched_doi": paper.doi,
                "entity_name": entity,
                "paper_title": paper.title,
                "paper_date": paper.paper_date,
                "pub_date": pr_row.pub_date,
                "embedding_sim": score,
                "pr_text": pr_row.pr_text,
            })
            entity_matches += 1

        elapsed = time.perf_counter() - entity_t0
        max_sim_s = f"{entity_max_sim:.3f}" if entity_max_sim is not None else "n/a"
        min_sim_s = f"{entity_min_sim_seen:.3f}" if entity_min_sim_seen is not None else "n/a"
        print(
            f"[{idx}/{n_entities}] {entity}: "
            f"prs={len(pr_sub):,}, dois={len(doi_sub):,}, "
            f"top1={entity_matches:,}/{entity_scored:,} dated, "
            f"sim=[{min_sim_s},{max_sim_s}], "
            f">={MIN_SIM}: {entity_ge_min:,}, {elapsed:.1f}s",
            flush=True,
        )

    total_elapsed = time.perf_counter() - t0
    print(
        f"Similarity match done: {len(matches):,} rows in {total_elapsed:.1f}s",
        flush=True,
    )

    out = pd.DataFrame(matches)
    con.register("_emb", out)
    con.execute("CREATE OR REPLACE TABLE embedding_title_match AS SELECT * FROM _emb")
    con.unregister("_emb")
    return len(out)


def main(
    run_pipeline_first: bool = True,
    min_sim: float | None = None,
    max_days: int = 348,
    rebuild: bool = False,
):
    """Run embedding match, then refresh matching-pipeline views/exports.

    Expects (or first builds) DOI/title/fuzzy/scope rows in ``pr_paper_matched`` so
    unmatched scope PRs are available as embedding candidates.

    By default each PR keeps its top same-entity DOI (no similarity floor).
    """
    from .eurekalert_duckdb import connect, setup_views
    from .fuzzy_title_match import MIN_SCORE, run_fuzzy_title_match
    from .matching_pipeline import (
        build_final,
        export_pass,
        match_embedding,
        match_doi,
        match_fuzzy,
        match_title,
        scope_only,
        setup,
    )

    if run_pipeline_first:
        # DOI/title/fuzzy first; empty embedding view; scope_only fills unmatched rows.
        from .matching_pipeline import main as run_matching_pipeline

        run_matching_pipeline()

    con = connect()
    setup_views(con)
    setup(con)

    # Ensure unmatched scope rows exist even if pipeline was skipped / stale.
    match_doi(con)
    match_title(con)
    match_fuzzy(con)
    match_embedding(con)
    scope_only(con)
    build_final(con)

    # Refresh fuzzy if skipped full pipeline (table may be missing/stale).
    if not run_pipeline_first:
        n_fuzzy = run_fuzzy_title_match(con, max_days=max_days)
        print(f"fuzzy_title_match: {n_fuzzy:,} rows (min_score={MIN_SCORE})")
        match_fuzzy(con)
        scope_only(con)
        build_final(con)

    n = run_embedding_match(con, min_sim=min_sim, max_days=max_days, rebuild=rebuild)
    thresh_s = f"min_sim={min_sim}" if min_sim is not None else "top-1 (no min_sim)"
    print(f"embedding_title_match: {n:,} rows ({thresh_s}, max_days={max_days})")

    match_embedding(con, min_sim=min_sim)
    scope_only(con)
    build_final(con)

    for name in (
        "doi_match",
        "title_match",
        "fuzzy_match",
        "embedding_match",
        "scope_only",
        "pr_paper_matched",
    ):
        export_pass(con, name)

    stats = con.execute("""
        SELECT match_method, confidence_tier, is_matched, count(*) AS n
        FROM pr_paper_matched
        GROUP BY 1, 2, 3 ORDER BY is_matched DESC, n DESC
    """).fetchall()
    print("pr_paper_matched:")
    for row in stats:
        print(f"  {row[0]:<22} tier={row[1]} matched={row[2]} n={row[3]:,}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Embedding title match after DOI/title/scope pipeline")
    p.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip 06_matching_pipeline; assume pr_paper_matched already exists",
    )
    p.add_argument(
        "--min-sim",
        type=float,
        default=None,
        help=f"Optional similarity floor (default: keep every PR's top DOI). "
        f"Example: --min-sim {MIN_SIM}",
    )
    p.add_argument("--max-days", type=int, default=348)
    p.add_argument("--rebuild", action="store_true", help="Rebuild embedding caches")
    args = p.parse_args()
    main(
        run_pipeline_first=not args.skip_pipeline,
        min_sim=args.min_sim,
        max_days=args.max_days,
        rebuild=args.rebuild,
    )
