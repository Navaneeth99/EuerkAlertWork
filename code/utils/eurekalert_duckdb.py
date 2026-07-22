"""
DuckDB setup for EurekAlert Parquet analysis.

Creates views over Processed/EurekAlert/*/*.parquet so you can query
~617K press releases without loading everything into pandas.

Views available after `setup`:
  press_releases          — all Press_release/*.parquet (617K rows)
  multimedia              — all Multimedia/*.parquet
  translations            — all Translations/*.parquet
  doi_list                — Processed/DOIList.csv (entity_name, doi, publication_date, title, …)
  press_releases_with_doi — press_releases joined to doi_list on DOI (includes paper_title)
  press_releases_from_2015 — Press_release parquet deliverables from 2015 onward (by file year)

Each EurekAlert view includes start_year and end_year columns (baked into
the Parquet files during extraction) for fast year-range filtering.

Usage:
  python code/05_eurekalert_duckdb.py setup          # register views
  python code/05_eurekalert_duckdb.py summary        # row counts + DOI coverage
  python code/05_eurekalert_duckdb.py sql "SELECT ..." # run one query
  python code/05_eurekalert_duckdb.py shell          # interactive SQL prompt
  python code/05_eurekalert_duckdb.py materialize    # copy into DuckDB tables

Requires: pip install duckdb pyarrow (see requirements.txt)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("Install duckdb: pip install duckdb", file=sys.stderr)
    sys.exit(1)

UTILS_DIR = Path(__file__).resolve().parent
CODE_DIR = UTILS_DIR.parent
PROJECT_DIR = CODE_DIR.parent
EUREKALERT_DIR = PROJECT_DIR / "Processed" / "EurekAlert"
DB_PATH = PROJECT_DIR / "Processed" / "eurekalert.duckdb"
QUERIES_PATH = CODE_DIR / "eurekalert_queries.sql"


DEFAULT_MIN_YEAR = 2015


def _parquet_glob(category: str) -> str:
    return (EUREKALERT_DIR / category / "*.parquet").as_posix()


def _parse_parquet_start_year(path: Path) -> int | None:
    """Return start_year from e.g. Press_release_2015_2015.parquet."""
    stem = path.stem
    prefix = f"{path.parent.name}_"
    if not stem.startswith(prefix):
        return None
    parts = stem.split("_")
    if len(parts) < 3:
        return None
    try:
        return int(parts[-2])
    except ValueError:
        return None


def _parquet_paths_from_year(category: str, min_year: int) -> list[str]:
    d = EUREKALERT_DIR / category
    paths: list[str] = []
    for path in sorted(d.glob("*.parquet")):
        start_year = _parse_parquet_start_year(path)
        if start_year is not None and start_year >= min_year:
            paths.append(path.as_posix())
    return paths


def _read_parquet_from_year_sql(category: str, min_year: int) -> str:
    paths = _parquet_paths_from_year(category, min_year)
    if not paths:
        raise FileNotFoundError(
            f"No {category} parquet files with start_year >= {min_year} under {EUREKALERT_DIR}"
        )
    files = ", ".join(f"'{p}'" for p in paths)
    return f"SELECT * FROM read_parquet([{files}], union_by_name=true)"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def _is_base_table(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_name = ? AND table_type = 'BASE TABLE'
        """,
        [name],
    ).fetchone()
    return bool(row and row[0])


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?",
        [name],
    ).fetchone()
    return bool(row and row[0])


def _view_or_table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_name = ?
        """,
        [name],
    ).fetchone()
    return bool(row and row[0])


def _eurekalert_select_sql(subdir: str) -> str:
    g = _parquet_glob(subdir)
    return f"SELECT * FROM read_parquet('{g}', union_by_name=true)"

def _doi_view_sql() -> str | None:
    doi_path = PROJECT_DIR / "Processed" / "DOIList.csv"
    if not doi_path.exists():
        return None
    p = doi_path.as_posix()
    # SELECT * so new columns (e.g. last_author_*) appear after re-extract.
    return f"""
        SELECT *
        FROM read_csv('{p}', header=true, auto_detect=true)
    """


def setup_views(con: duckdb.DuckDBPyConnection) -> None:
    """Register views over Parquet files. Skips if tables already materialized."""
    for name, sql in (
        ("press_releases", _eurekalert_select_sql("Press_release")),
        ("multimedia", _eurekalert_select_sql("Multimedia")),
        ("translations", _eurekalert_select_sql("Translations")),
    ):
        if _table_exists(con, name):
            continue
        con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")

    doi_sql = _doi_view_sql()
    if doi_sql and not _table_exists(con, "doi_list"):
        con.execute(f"CREATE OR REPLACE VIEW doi_list AS {doi_sql}")

    if _view_or_table_exists(con, "press_releases") and _view_or_table_exists(con, "doi_list"):
        if not _table_exists(con, "press_releases_with_doi"):
            con.execute("""
                CREATE OR REPLACE VIEW press_releases_with_doi AS
                SELECT
                    pr.*,
                    dl.entity_name,
                    dl.openalex_id,
                    dl.category AS openalex_category,
                    dl.publication_date AS paper_publication_date,
                    dl.title AS paper_title,
                    dl.cited_by_count AS paper_cited_by_count
                FROM press_releases pr
                LEFT JOIN doi_list dl
                    ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
                WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != ''
            """)

    if EUREKALERT_DIR.is_dir() and not _is_base_table(con, "press_releases_from_2015"):
        con.execute("DROP VIEW IF EXISTS press_releases_with_pub_date_2015")
        con.execute(f"""
            CREATE OR REPLACE VIEW press_releases_from_2015 AS
            {_read_parquet_from_year_sql("Press_release", DEFAULT_MIN_YEAR)}
        """)


def materialize_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Copy Parquet files into native DuckDB tables for fastest repeated queries."""
    for name in ("press_releases", "multimedia", "translations", "doi_list", "press_releases_with_doi"):
        con.execute(f"DROP TABLE IF EXISTS {name}")

    print("Materializing press_releases...")
    con.execute(f"CREATE TABLE press_releases AS {_eurekalert_select_sql('Press_release')}")
    print("Materializing multimedia...")
    con.execute(f"CREATE TABLE multimedia AS {_eurekalert_select_sql('Multimedia')}")
    print("Materializing translations...")
    con.execute(f"CREATE TABLE translations AS {_eurekalert_select_sql('Translations')}")

    doi_sql = _doi_view_sql()
    if doi_sql:
        print("Materializing doi_list...")
        con.execute(f"CREATE TABLE doi_list AS {doi_sql}")
        con.execute("""
            CREATE OR REPLACE TABLE press_releases_with_doi AS
            SELECT
                pr.*,
                dl.entity_name,
                dl.openalex_id,
                dl.category AS openalex_category,
                dl.publication_date AS paper_publication_date,
                dl.title AS paper_title,
                dl.cited_by_count AS paper_cited_by_count
            FROM press_releases pr
            LEFT JOIN doi_list dl ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
            WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != ''
        """)


def print_summary(con: duckdb.DuckDBPyConnection) -> None:
    setup_views(con)
    rows = con.execute("""
        SELECT 'press_releases' AS name, count(*)::BIGINT AS rows FROM press_releases
        UNION ALL
        SELECT 'multimedia',   count(*) FROM multimedia
        UNION ALL
        SELECT 'translations', count(*) FROM translations
    """).fetchall()
    print("\nRow counts:")
    for name, n in rows:
        print(f"  {name}: {n:,}")

    doi_stats = con.execute("""
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE "DOI" IS NOT NULL AND trim("DOI") != '') AS with_doi
        FROM press_releases
    """).fetchone()
    print(f"\nPress releases with DOI: {doi_stats[1]:,} / {doi_stats[0]:,}")

    if _view_or_table_exists(con, "doi_list"):
        matched = con.execute("""
            SELECT count(DISTINCT pr."PR ID")
            FROM press_releases pr
            INNER JOIN doi_list dl ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
            WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != ''
        """).fetchone()[0]
        print(f"Press releases matching DOIList.csv: {matched:,}")


def run_sql(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    setup_views(con)
    result = con.execute(sql)
    if result.description:
        print(result.df().to_string(index=False))
    else:
        print("OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="DuckDB helper for EurekAlert Parquet files")
    parser.add_argument(
        "command",
        choices=["setup", "materialize", "summary", "sql", "shell"],
        help=(
            "setup=register views  materialize=copy into DuckDB tables  "
            "summary=row counts  sql=run query  shell=interactive prompt"
        ),
    )
    parser.add_argument("query", nargs="?", help="SQL string for the 'sql' command")
    args = parser.parse_args()

    if not EUREKALERT_DIR.is_dir():
        print(f"EurekAlert data not found: {EUREKALERT_DIR}", file=sys.stderr)
        return 1

    con = connect()

    if args.command == "setup":
        setup_views(con)
        print(f"Views registered in {DB_PATH}")
        print("  press_releases, multimedia, translations")
        if (PROJECT_DIR / "Processed" / "DOIList.csv").exists():
            print("  doi_list, press_releases_with_doi, press_releases_from_2015")
        print(f"\nExample:")
        print(f'  python code/05_eurekalert_duckdb.py sql "SELECT count(*) FROM press_releases"')
        if QUERIES_PATH.exists():
            print(f"Starter queries: {QUERIES_PATH}")

    elif args.command == "materialize":
        materialize_tables(con)
        print(f"\nTables materialized in {DB_PATH}")

    elif args.command == "summary":
        print_summary(con)

    elif args.command == "sql":
        if not args.query:
            print("Provide SQL as the second argument", file=sys.stderr)
            return 1
        run_sql(con, args.query)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
