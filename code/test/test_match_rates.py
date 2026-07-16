"""Per-entity DOI match rates for organisations/journals.

Reports what share of press releases for each entity_name were matched to a DOI
(via DOI, exact title, or embedding), using ``pr_paper_matched``.

Also reports embedding-only rates on ``embedding_title_match`` (same query as
analysis.ipynb).

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
        """
        SELECT
            entity_name,
            count(*) AS n_prs,
            sum(is_matched) AS n_matched,
            sum(is_matched) * 1.0 / count(*) AS match_percentage
        FROM pr_paper_matched
        WHERE entity_name IS NOT NULL AND trim(entity_name) != ''
        GROUP BY entity_name
        ORDER BY n_prs DESC, entity_name
        """
    ).df()


def match_rates_by_method(con):
    """Per-entity counts by match_method (doi / exact_title / embedding / scope)."""
    return con.sql(
        """
        SELECT
            entity_name,
            match_method,
            confidence_tier,
            count(*) AS n_prs,
            sum(is_matched) AS n_matched
        FROM pr_paper_matched
        WHERE entity_name IS NOT NULL AND trim(entity_name) != ''
        GROUP BY 1, 2, 3
        ORDER BY entity_name, n_prs DESC
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

    print("=== Overall DOI match rate by entity (pr_paper_matched) ===")
    print(overall.to_string(index=False))
    print()
    print(
        f"Entities: {len(overall):,}  |  "
        f"PRs: {int(overall['n_prs'].sum()):,}  |  "
        f"Matched: {int(overall['n_matched'].sum()):,}  |  "
        f"Overall rate: {overall['n_matched'].sum() / overall['n_prs'].sum():.1%}"
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
