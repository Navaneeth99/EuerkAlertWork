"""Embedding title match after DOI/title/scope matching.

Runs ``06_matching_pipeline`` (unless ``--skip-pipeline``), then
``utils.embedding_match``, then refreshes ``embedding_match`` / ``scope_only`` /
``pr_paper_matched`` and re-exports CSVs.

By default each unmatched PR keeps its top same-entity DOI (no 0.7 floor).

Usage:
  python code/06b_embedding_match.py
  python code/06_matching_pipeline.py && python code/06b_embedding_match.py --skip-pipeline
  python code/06b_embedding_match.py --min-sim 0.7
  python code/06b_embedding_match.py --rebuild
"""
import sys
from pathlib import Path

# Allow `python code/06b_embedding_match.py` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.embedding_match import MIN_SIM, main

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip 06_matching_pipeline; assume it already ran",
    )
    p.add_argument(
        "--min-sim",
        type=float,
        default=None,
        help=f"Optional similarity floor (default: keep every top DOI). "
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
