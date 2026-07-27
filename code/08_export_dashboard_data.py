"""
Export paper-level impact data for the Streamlit dashboard.

Builds paper_df from DuckDB + Altmetric once, then writes:
  - Processed/dashboard/paper_df.parquet
  - overview + FE coefficient CSVs for every non-empty category combination

Paper rows keep OpenAlex ``entity_name`` / ``category`` from ``doi_list``.
Matched press releases also contribute nullable PR-scope columns from
``pr_paper_matched``:

  - pr_journal
  - pr_institution
  - pr_publisher

Requires a current matching pipeline run so ``pr_paper_matched`` has the
triple entity columns:

    python code/06_matching_pipeline.py

Usage:
    python code/08_export_dashboard_data.py
    python code/08_export_dashboard_data.py --sample-size 50000
    python code/08_export_dashboard_data.py --no-coefficients
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from utils.impact_analysis import (  # noqa: E402
    DEFAULT_ALTMET_CSV,
    DEFAULT_DASHBOARD_DIR,
    DEFAULT_DUCKDB,
    count_csv_data_rows,
    load_paper_df,
    save_dashboard_cache,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export dashboard parquet cache under Processed/dashboard/ "
            "(includes pr_journal / pr_institution / pr_publisher)."
        )
    )
    parser.add_argument("--duckdb", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--altmet-csv", type=Path, default=DEFAULT_ALTMET_CSV)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_DASHBOARD_DIR,
        help="Output directory (default: Processed/dashboard)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Max rows per has_pr group when building (0 = all rows; export only)",
    )
    parser.add_argument(
        "--no-coefficients",
        action="store_true",
        help="Skip FE coefficient CSVs per category combo (faster export)",
    )
    return parser.parse_args()


def _print_pr_entity_fill(paper_df) -> None:
    with_pr = paper_df.loc[paper_df["has_pr"]]
    n = len(with_pr)
    if n == 0:
        print("  PR entity fill: no papers with has_pr=True")
        return

    def filled(col: str) -> int:
        s = with_pr[col]
        mask = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).str.lower().ne(
            "nan"
        )
        return int(mask.sum())

    print(
        f"  PR entity fill (among {n:,} papers with PR): "
        f"journal={filled('pr_journal'):,}  "
        f"institution={filled('pr_institution'):,}  "
        f"publisher={filled('pr_publisher'):,}"
    )


def main() -> None:
    args = parse_args()
    sample_size = None if args.sample_size == 0 else args.sample_size

    if not args.duckdb.exists():
        raise SystemExit(f"DuckDB not found: {args.duckdb}")
    if not args.altmet_csv.exists():
        raise SystemExit(f"Altmetric CSV not found: {args.altmet_csv}")

    print("Building paper_df from DuckDB + Altmetric (one-time) …")
    paper_df = load_paper_df(
        duckdb_path=args.duckdb,
        altmet_csv=args.altmet_csv,
        sample_size=sample_size,
    )
    print(
        f"Loaded {len(paper_df):,} papers "
        f"({int(paper_df['has_pr'].sum()):,} with PR)."
    )
    _print_pr_entity_fill(paper_df)

    n_altmet_source = count_csv_data_rows(args.altmet_csv)
    print(f"Writing cache to {args.out_dir.resolve()} …")
    paths = save_dashboard_cache(
        paper_df,
        out_dir=args.out_dir,
        include_coefficients=not args.no_coefficients,
        n_altmet_source=n_altmet_source or None,
    )
    for name, path in paths.items():
        print(f"  {name}: {path} ({path.stat().st_size / 1e6:.1f} MB)")
    print("Done. Launch the dashboard with:")
    print("  streamlit run code/dashboard/app.py")


if __name__ == "__main__":
    main()
