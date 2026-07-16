"""
Extract EurekAlert! Excel deliverables to Parquet.

Reads each eareleases_{start_year}-{end_year}.xlsx from rawdata/EurekAlertData/
and exports three sheets to separate Parquet files:

  Processed/EurekAlert/Press_release/{category}_{start_year}_{end_year}.parquet
  Processed/EurekAlert/Multimedia/{category}_{start_year}_{end_year}.parquet
  Processed/EurekAlert/Translations/{category}_{start_year}_{end_year}.parquet

Each Parquet file has two extra columns: start_year and end_year (parsed from
the filename) so DuckDB can filter by year without re-reading all files.

Requires: pip install pandas openpyxl pyarrow
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_DIR / "rawdata" / "EurekAlertData"
OUTPUT_BASE = PROJECT_DIR / "Processed" / "EurekAlert"

FILE_PATTERN = re.compile(r"^eareleases_(\d{4})[-_](\d{4})\.xlsx$", re.IGNORECASE)

SHEETS = {
    "Press Releases": ("Press_release", "Press_release"),
    "Multimedia":     ("Multimedia",     "Multimedia"),
    "Translations":   ("Translations",   "Translations"),
}


def parse_workbook_path(path: Path) -> tuple[int, int] | None:
    """Return (start_year, end_year) from filename, or None if not a data file."""
    if path.name.startswith(".~lock") or path.name.startswith("~$"):
        return None
    match = FILE_PATTERN.match(path.name)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def export_sheet(
    workbook: Path,
    sheet_name: str,
    output_dir: Path,
    category: str,
    start_year: int,
    end_year: int,
    skip_existing: bool = True,
) -> int:
    """Read one sheet and write Parquet. Returns row count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{category}_{start_year}_{end_year}.parquet"

    if skip_existing and output_path.exists():
        import pyarrow.parquet as pq
        return pq.read_metadata(output_path).num_rows

    df = pd.read_excel(workbook, sheet_name=sheet_name, engine="openpyxl", dtype=str)

    # Ensure all text columns are str (not object with mixed types)
    df = df.where(df.notna(), other=None)

    # Embed year metadata as columns so DuckDB can filter without touching every file
    df.insert(0, "start_year", start_year)
    df.insert(1, "end_year", end_year)

    df.to_parquet(output_path, index=False, engine="pyarrow")
    return len(df)


def process_workbook(path: Path, skip_existing: bool = True) -> list[tuple[str, int]]:
    """Export all sheets from one workbook. Returns list of (label, row_count)."""
    years = parse_workbook_path(path)
    if years is None:
        return []

    start_year, end_year = years
    results: list[tuple[str, int]] = []

    for sheet_name, (out_dir_name, category) in SHEETS.items():
        out_dir = OUTPUT_BASE / out_dir_name
        rows = export_sheet(
            path, sheet_name, out_dir, category, start_year, end_year,
            skip_existing=skip_existing,
        )
        label = f"{category}_{start_year}_{end_year}.parquet"
        results.append((label, rows))

    return results


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Extract EurekAlert XLSXs to Parquet")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Re-extract even if output Parquet already exists",
    )
    args = parser.parse_args()
    skip_existing = not args.overwrite

    if not INPUT_DIR.is_dir():
        print(f"Input directory not found: {INPUT_DIR}", file=sys.stderr)
        return 1

    workbooks = sorted(
        p for p in INPUT_DIR.glob("*.xlsx") if parse_workbook_path(p) is not None
    )

    if not workbooks:
        print(f"No eareleases_*.xlsx files found in {INPUT_DIR}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("EurekAlert Excel → Parquet extraction")
    print("=" * 60)
    print(f"Input:   {INPUT_DIR}")
    print(f"Output:  {OUTPUT_BASE}")
    print(f"Found {len(workbooks)} workbook(s)\n")

    total_files = 0
    total_rows = 0
    for i, workbook in enumerate(workbooks, start=1):
        print(f"[{i}/{len(workbooks)}] {workbook.name}")
        try:
            for label, rows in process_workbook(workbook, skip_existing=skip_existing):
                skipped = " (skipped, already exists)" if skip_existing and rows >= 0 else ""
                print(f"  {label}: {rows:,} rows{skipped}")
                total_files += 1
                total_rows += rows
        except Exception as exc:
            print(f"  Error: {exc}", file=sys.stderr)
            return 1

    print("\n" + "=" * 60)
    print(f"Done. {total_files} Parquet file(s), {total_rows:,} total rows")
    print(f"Output: {OUTPUT_BASE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
