"""Export pr_paper_matched joined to full PR rows + DOIList fields.

Columns:
  - press-release columns from pr_base (excluding Summary and Full Text)
  - journal, institution, publisher, match_method, confidence_tier, is_matched
  - for matched rows: entity_name, doi, publication_date from DOIList
    (prefixed doi_list_* to avoid clashing with PR DOI / Publication Date)

Usage:
  python code/test/export_pr_paper_matched.py
  python code/test/export_pr_paper_matched.py --out Processed/pr_doi_joined/pr_paper_matched_full.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT = CODE_DIR.parent
sys.path.insert(0, str(CODE_DIR))

DEFAULT_OUT = ROOT / "Processed" / "pr_doi_joined" / "pr_paper_matched_full.csv"


def export_pr_paper_matched_full(con, out: Path = DEFAULT_OUT) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    path = tmp.resolve().as_posix()

    # Prefer doi_list row matching any of the PR's filled entity columns.
    # Drop Summary / Full Text to keep the export smaller.
    con.execute(f"""
        COPY (
            SELECT
                pr.* EXCLUDE ("Summary", "Full Text"),
                m.journal,
                m.institution,
                m.publisher,
                m.match_method,
                m.confidence_tier,
                m.is_matched,
                dl.entity_name AS doi_list_entity_name,
                dl.category AS doi_list_category,
                dl.doi AS doi_list_doi,
                dl.publication_date AS doi_list_publication_date
            FROM pr_paper_matched m
            JOIN pr_base pr
              ON CAST(pr."PR ID" AS VARCHAR) = CAST(m.pr_id AS VARCHAR)
            LEFT JOIN LATERAL (
                SELECT d.entity_name, d.category, d.doi, d.publication_date
                FROM doi_list d
                WHERE m.is_matched = 1
                  AND m.matched_doi IS NOT NULL
                  AND trim(CAST(m.matched_doi AS VARCHAR)) != ''
                  AND lower(trim(d.doi)) = lower(trim(CAST(m.matched_doi AS VARCHAR)))
                ORDER BY CASE
                    WHEN m.journal IS NOT NULL AND d.entity_name = m.journal THEN 0
                    WHEN m.institution IS NOT NULL AND d.entity_name = m.institution THEN 1
                    WHEN m.publisher IS NOT NULL AND d.entity_name = m.publisher THEN 2
                    ELSE 3
                END,
                d.entity_name
                LIMIT 1
            ) dl ON true
        ) TO '{path}' (HEADER, DELIMITER ',', FORMAT CSV)
    """)

    try:
        if out.exists():
            out.unlink()
        tmp.replace(out)
        final = out
    except PermissionError:
        # Original file may be open in Excel/IDE — keep a sibling file instead.
        final = out.with_name(out.stem + "_nosummary" + out.suffix)
        if final.exists():
            final.unlink()
        tmp.replace(final)
        print(f"Could not replace {out} (file in use); wrote {final}")

    n = con.execute(
        f"SELECT count(*) FROM read_csv_auto('{final.resolve().as_posix()}', header=true)"
    ).fetchone()[0]
    print(f"Wrote {n:,} rows -> {final}")
    return final


def main(out: Path = DEFAULT_OUT) -> None:
    from utils.eurekalert_duckdb import connect, setup_views
    from utils.matching_pipeline import setup

    con = connect()
    setup_views(con)
    # Ensure pr_base / matching views exist if DB only has tables from a prior run.
    try:
        con.execute("SELECT 1 FROM pr_paper_matched LIMIT 1")
        con.execute("SELECT 1 FROM pr_base LIMIT 1")
    except Exception:
        setup(con)

    export_pr_paper_matched_full(con, out=out)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    main(out=args.out)
