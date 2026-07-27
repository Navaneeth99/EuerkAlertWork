"""Per-entity DOI match rates for organisations/journals/publishers.

Reports what share of press releases for each journal / institution / publisher
were matched to a DOI (via DOI, exact title, fuzzy, or embedding), using
``pr_paper_matched`` with the three nullable entity columns unpivoted.

Also reports embedding-only rates on ``embedding_title_match`` and column fill
rates.

Requires the matching pipeline (and preferably embedding match) to have run:
  python code/06_matching_pipeline.py
  python code/06b_embedding_match.py --skip-pipeline

Usage:
  python code/test/test_match_rates.py
  python code/test/test_match_rates.py --min-sim 0.7 --out Processed/match_rates.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from utils.embedding_match import MIN_SIM  # noqa: E402
from utils.eurekalert_duckdb import connect  # noqa: E402

ROOT = CODE_DIR.parent
DEFAULT_OUT = ROOT / "Processed" / "pr_doi_joined" / "match_rates_by_entity.csv"

# Unpivot journal / institution / publisher into long form.
ENTITY_UNPIVOT = """
SELECT pr_id, journal AS entity_name, 'journal' AS entity_category, is_matched
FROM pr_paper_matched
WHERE journal IS NOT NULL AND trim(journal) != ''
UNION ALL
SELECT pr_id, institution AS entity_name, 'institution' AS entity_category, is_matched
FROM pr_paper_matched
WHERE institution IS NOT NULL AND trim(institution) != ''
UNION ALL
SELECT pr_id, publisher AS entity_name, 'publisher' AS entity_category, is_matched
FROM pr_paper_matched
WHERE publisher IS NOT NULL AND trim(publisher) != ''
"""


def _require(con, name: str) -> None:
    n = con.execute(
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [name],
    ).fetchone()[0]
    if not n:
        raise RuntimeError(
            f"Missing DuckDB object `{name}`. "
            "Run python code/06_matching_pipeline.py "
            "(and code/06b_embedding_match.py for embedding rates) first."
        )


def match_rates_overall(con):
    """% of scoped PRs per entity with a DOI match (any method)."""
    return con.sql(
        f"""
        SELECT
            entity_name,
            entity_category,
            count(*) AS n_prs,
            sum(is_matched) AS n_matched,
            sum(is_matched) * 1.0 / count(*) AS match_percentage
        FROM ({ENTITY_UNPIVOT}) e
        GROUP BY entity_name, entity_category
        ORDER BY n_prs DESC, entity_category, entity_name
        """
    ).df()


def column_fill_rates(con):
    """How often each entity column is non-null on pr_paper_matched."""
    return con.sql(
        """
        SELECT
            count(*) AS n_prs,
            sum(CASE WHEN journal IS NOT NULL AND trim(journal) != '' THEN 1 ELSE 0 END)
                AS n_with_journal,
            sum(CASE WHEN institution IS NOT NULL AND trim(institution) != '' THEN 1 ELSE 0 END)
                AS n_with_institution,
            sum(CASE WHEN publisher IS NOT NULL AND trim(publisher) != '' THEN 1 ELSE 0 END)
                AS n_with_publisher,
            sum(is_matched) AS n_matched,
            sum(is_matched) * 1.0 / count(*) AS paper_match_percentage
        FROM pr_paper_matched
        """
    ).df()


def match_rates_by_method(con):
    """Per-entity counts by match_method (doi / exact_title / embedding / scope)."""
    return con.sql(
        f"""
        SELECT
            e.entity_name,
            e.entity_category,
            m.match_method,
            m.confidence_tier,
            count(*) AS n_prs,
            sum(e.is_matched) AS n_matched
        FROM ({ENTITY_UNPIVOT}) e
        JOIN pr_paper_matched m ON e.pr_id = m.pr_id
        GROUP BY 1, 2, 3, 4
        ORDER BY e.entity_name, e.entity_category, n_prs DESC
        """
    ).df()


def match_rates_embedding(con, min_sim: float = MIN_SIM):
    """Embedding-candidate match rate per entity (analysis.ipynb query)."""
    return con.sql(
        f"""
        SELECT
            entity_name,
            count(*) AS n_prs,
            sum(CASE WHEN embedding_sim > {min_sim} THEN 1 ELSE 0 END) AS n_matched,
            sum(CASE WHEN embedding_sim > {min_sim} THEN 1 ELSE 0 END) * 1.0
                / count(*) AS match_percentage
        FROM embedding_title_match
        GROUP BY entity_name
        ORDER BY n_prs DESC, entity_name
        """
    ).df()


def main(min_sim: float = MIN_SIM, out: Path | None = DEFAULT_OUT) -> None:
    con = connect(read_only=True)
    _require(con, "pr_paper_matched")

    overall = match_rates_overall(con)
    by_method = match_rates_by_method(con)
    fill = column_fill_rates(con)

    print("=== Column fill rates (pr_paper_matched) ===")
    print(fill.to_string(index=False))
    print()
    print("=== Overall DOI match rate by entity (unpivoted) ===")
    print(overall.to_string(index=False))
    print()
    print(
        f"Entity rows: {len(overall):,}  |  "
        f"PR-entity links: {int(overall['n_prs'].sum()):,}  |  "
        f"Matched links: {int(overall['n_matched'].sum()):,}  |  "
        f"Link match rate: {overall['n_matched'].sum() / overall['n_prs'].sum():.1%}"
    )

    has_embedding = (
        con.execute(
            """
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = 'embedding_title_match'
            """
        ).fetchone()[0]
        > 0
    )
    embedding = None
    if has_embedding:
        embedding = match_rates_embedding(con, min_sim=min_sim)
        print()
        print(
            f"=== Embedding match rate by entity "
            f"(embedding_sim > {min_sim}) ==="
        )
        print(embedding.to_string(index=False))
    else:
        print()
        print("(skip embedding rates: embedding_title_match not found)")

    if out is not None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        overall.to_csv(out, index=False)
        fill.to_csv(out.with_name("match_rates_column_fill.csv"), index=False)
        by_method.to_csv(out.with_name("match_rates_by_entity_method.csv"), index=False)
        if embedding is not None:
            embedding.to_csv(
                out.with_name("match_rates_by_entity_embedding.csv"), index=False
            )
        print()
        print(f"Wrote {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--min-sim", type=float, default=MIN_SIM)
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="CSV path for overall rates (sibling files for method/embedding)",
    )
    p.add_argument("--no-out", action="store_true", help="Print only; do not write CSVs")
    args = p.parse_args()
    main(min_sim=args.min_sim, out=None if args.no_out else args.out)
