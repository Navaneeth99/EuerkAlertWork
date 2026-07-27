"""Per-entity PR and DOI counts.

Writes one row per entity_name with:
  - n_dois: papers in DOIList
  - n_prs: press releases (see --strong-scope)
  - n_prs_matched: DOI/title/embedding matches from pr_paper_matched

Usage:
  python code/test/entity_pr_doi_counts.py
  python code/test/entity_pr_doi_counts.py --strong-scope
  python code/test/entity_pr_doi_counts.py --category institution
  python code/test/entity_pr_doi_counts.py --out Processed/pr_doi_joined/entity_pr_doi_counts.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
ROOT = CODE_DIR.parent
sys.path.insert(0, str(CODE_DIR))

DEFAULT_OUT = ROOT / "Processed" / "pr_doi_joined" / "entity_pr_doi_counts.csv"
DEFAULT_STRONG_OUT = (
    ROOT / "Processed" / "pr_doi_joined" / "entity_pr_doi_counts_strong_scope.csv"
)

# Stronger scope signals: org / journal fields (excludes summary- and full-text-only).
STRONG_SCOPE_PRED = """
(
  matched_in_organization_flag = 1
  OR matched_in_journal_typed_flag = 1
  OR matched_in_journal_matched_flag = 1
)
"""

ENTITY_UNPIVOT = """
SELECT pr_id, journal AS entity_name, is_matched
FROM pr_paper_matched
WHERE journal IS NOT NULL AND trim(journal) != ''
UNION ALL
SELECT pr_id, institution AS entity_name, is_matched
FROM pr_paper_matched
WHERE institution IS NOT NULL AND trim(institution) != ''
UNION ALL
SELECT pr_id, publisher AS entity_name, is_matched
FROM pr_paper_matched
WHERE publisher IS NOT NULL AND trim(publisher) != ''
"""


def _from_duckdb(category: str | None, strong_scope: bool):
    from utils.eurekalert_duckdb import connect, setup_views

    con = connect(read_only=True)
    try:
        con.execute("SELECT 1 FROM doi_list LIMIT 1")
    except Exception:
        setup_views(con)

    cat_pred = ""
    if category:
        cat_pred = (
            "AND lower(trim(coalesce(d.category, ''))) = "
            f"'{category.lower().strip()}'"
        )

    has_scope_long = con.execute(
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = 'scope_name_text_search_long'
        """
    ).fetchone()[0]
    has_pr = con.execute(
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = 'pr_paper_matched'
        """
    ).fetchone()[0]

    if strong_scope:
        if not has_scope_long:
            raise RuntimeError(
                "scope_name_text_search_long missing; "
                "run python code/06_matching_pipeline.py"
            )
        matched_cte = ""
        matched_cols = "0 AS n_prs_matched,"
        matched_join = ""
        if has_pr:
            matched_cte = f""",
            matched AS (
                SELECT entity_name, sum(is_matched) AS n_prs_matched
                FROM ({ENTITY_UNPIVOT}) e
                GROUP BY entity_name
            )"""
            matched_cols = "coalesce(m.n_prs_matched, 0) AS n_prs_matched,"
            matched_join = (
                "LEFT JOIN matched m ON coalesce(d.entity_name, p.canonical_name) = m.entity_name"
            )

        return con.sql(
            f"""
            WITH dois AS (
                SELECT
                    entity_name,
                    any_value(category) AS category,
                    count(*) AS n_dois,
                    count(DISTINCT doi) AS n_unique_dois
                FROM doi_list
                WHERE entity_name IS NOT NULL AND trim(entity_name) != ''
                GROUP BY entity_name
            ),
            scope_all AS (
                SELECT canonical_name, count(DISTINCT "PR ID") AS n_prs_all
                FROM scope_name_text_search_long
                GROUP BY canonical_name
            ),
            scope_strong AS (
                SELECT canonical_name, count(DISTINCT "PR ID") AS n_prs
                FROM scope_name_text_search_long
                WHERE {STRONG_SCOPE_PRED}
                GROUP BY canonical_name
            )
            {matched_cte}
            SELECT
                coalesce(d.entity_name, p.canonical_name) AS entity_name,
                d.category,
                coalesce(p.n_prs, 0) AS n_prs,
                coalesce(a.n_prs_all, 0) AS n_prs_all,
                {matched_cols}
                coalesce(d.n_dois, 0) AS n_dois,
                coalesce(d.n_unique_dois, 0) AS n_unique_dois
            FROM dois d
            FULL OUTER JOIN scope_strong p ON d.entity_name = p.canonical_name
            LEFT JOIN scope_all a
              ON coalesce(d.entity_name, p.canonical_name) = a.canonical_name
            {matched_join}
            WHERE 1 = 1
              {cat_pred}
            ORDER BY n_prs DESC, n_dois DESC, entity_name
            """
        ).df()

    if has_pr:
        return con.sql(
            f"""
            WITH dois AS (
                SELECT
                    entity_name,
                    any_value(category) AS category,
                    count(*) AS n_dois,
                    count(DISTINCT doi) AS n_unique_dois
                FROM doi_list
                WHERE entity_name IS NOT NULL AND trim(entity_name) != ''
                GROUP BY entity_name
            ),
            prs AS (
                SELECT
                    entity_name,
                    count(*) AS n_prs,
                    sum(is_matched) AS n_prs_matched
                FROM ({ENTITY_UNPIVOT}) e
                GROUP BY entity_name
            )
            SELECT
                coalesce(d.entity_name, p.entity_name) AS entity_name,
                d.category,
                coalesce(p.n_prs, 0) AS n_prs,
                coalesce(p.n_prs_matched, 0) AS n_prs_matched,
                coalesce(d.n_dois, 0) AS n_dois,
                coalesce(d.n_unique_dois, 0) AS n_unique_dois
            FROM dois d
            FULL OUTER JOIN prs p ON d.entity_name = p.entity_name
            WHERE 1 = 1
              {cat_pred}
            ORDER BY n_prs DESC, n_dois DESC, entity_name
            """
        ).df()

    cat_filter = ""
    if category:
        cat_filter = f"AND lower(trim(category)) = '{category.lower().strip()}'"
    return con.sql(
        f"""
        SELECT
            entity_name,
            any_value(category) AS category,
            0 AS n_prs,
            0 AS n_prs_matched,
            count(*) AS n_dois,
            count(DISTINCT doi) AS n_unique_dois
        FROM doi_list
        WHERE entity_name IS NOT NULL AND trim(entity_name) != ''
          {cat_filter}
        GROUP BY entity_name
        ORDER BY n_dois DESC, entity_name
        """
    ).df()


def main(
    out: Path | None = None,
    category: str | None = None,
    strong_scope: bool = False,
) -> Path:
    if out is None:
        out = DEFAULT_STRONG_OUT if strong_scope else DEFAULT_OUT

    df = _from_duckdb(category, strong_scope=strong_scope)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} entities -> {out}")
    if strong_scope and "n_prs_all" in df.columns:
        print(
            "(n_prs = org/journal-typed/journal-matched only; "
            "n_prs_all = all scope hits incl. summary/full-text)"
        )
    print(df.head(25).to_string(index=False))
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--category",
        default=None,
        help="Optional filter: institution | journal | publisher",
    )
    p.add_argument(
        "--strong-scope",
        action="store_true",
        help=(
            "Count PRs only if matched_in_organization_flag OR "
            "matched_in_journal_typed_flag OR matched_in_journal_matched_flag = 1"
        ),
    )
    args = p.parse_args()
    main(out=args.out, category=args.category, strong_scope=args.strong_scope)
