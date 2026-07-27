"""Press release -> paper matching helpers.

Usage: python code/06_matching_pipeline.py

Each PR keeps one matched paper (DOI/title/fuzzy/embedding cascade) and up to
three nullable entity columns: journal, institution, publisher.
"""

from pathlib import Path

from .eurekalert_duckdb import connect, setup_views

UTILS_DIR = Path(__file__).resolve().parent
CODE_DIR = UTILS_DIR.parent
ROOT = CODE_DIR.parent
SCOPE_NAME_SQL = UTILS_DIR / "scope_name_text_search.sql"
ALTERNATE_TITLES_JSON = (
    ROOT / "rawdata" / "Institution_OpenAlexCrossWalk" / "openalex_alternate_titles.json"
)
EXPORT = ROOT / "Processed" / "pr_doi_joined"

DOI_CLEAN = """
CASE
  WHEN regexp_replace("DOI", ' ', '') ILIKE 'https://doi.org/%' THEN substr(regexp_replace("DOI", ' ', ''), 17)
  WHEN regexp_replace("DOI", ' ', '') ILIKE 'http://doi.org/%' THEN substr(regexp_replace("DOI", ' ', ''), 16)
  WHEN regexp_replace("DOI", ' ', '') ILIKE 'doi.org/%' THEN substr(regexp_replace("DOI", ' ', ''), 9)
  WHEN regexp_replace("DOI", ' ', '') ILIKE 'DOI:%' THEN trim(substr(regexp_replace("DOI", ' ', ''), 5))
  ELSE NULLIF(trim(regexp_replace("DOI", ' ', '')), '')
END
"""

DOI_RX = r"'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)'"
DOI_FROM_TEXT = f"regexp_extract(coalesce(\"Summary\", \"Full Text\", ''), {DOI_RX}, 1)"

# Shared paper-match column list (entity columns attached in build_final).
_PAPER_COLS = """
    pr_id, matched_doi, paper_title, paper_date, pub_date,
    match_method, confidence_tier, is_matched
"""


def setup(con):
    con.execute(f"""
        CREATE OR REPLACE VIEW pr_base AS
        SELECT
            pr.*,
            {DOI_CLEAN} AS cleaned_doi,
            {DOI_FROM_TEXT} AS doi_from_pr,
            lower(trim(coalesce({DOI_CLEAN}, {DOI_FROM_TEXT}))) AS final_doi,
            CAST("Publication Date" AS DATE) AS pub_date
        FROM press_releases_from_2015 pr
        WHERE
            ({DOI_CLEAN} IS NOT NULL AND trim({DOI_CLEAN}) != '')
            OR ({DOI_FROM_TEXT} IS NOT NULL AND trim({DOI_FROM_TEXT}) != '')
            OR ("Article Title" IS NOT NULL AND trim("Article Title") != '')
            OR (Organization IS NOT NULL AND trim(Organization) != '')
    """)
    con.execute(
        "CREATE OR REPLACE VIEW doi_list_norm AS "
        "SELECT *, lower(trim(doi)) AS doi_norm FROM doi_list"
    )

    if not ALTERNATE_TITLES_JSON.exists():
        raise FileNotFoundError(
            f"Missing alternate titles JSON: {ALTERNATE_TITLES_JSON}\n"
            "Run: python code/01a_extract_alternate_titles.py"
        )
    scope_sql = SCOPE_NAME_SQL.read_text(encoding="utf-8").replace(
        "{{OPENALEX_ALTERNATE_TITLES_JSON}}",
        ALTERNATE_TITLES_JSON.resolve().as_posix(),
    )
    con.execute(scope_sql)

    # Wide one-row-per-PR view used by matching + exports.
    con.execute("""
        CREATE OR REPLACE TABLE scope_name_text_search AS
        SELECT
            "PR ID",
            max(CASE WHEN entity_category = 'journal' THEN canonical_name END)
                AS journal,
            max(CASE WHEN entity_category = 'institution' THEN canonical_name END)
                AS institution,
            max(CASE WHEN entity_category = 'publisher' THEN canonical_name END)
                AS publisher
        FROM scope_name_text_search_long
        GROUP BY "PR ID"
    """)

    # Long form for fuzzy/embedding candidate pools (one row per filled category).
    con.execute("""
        CREATE OR REPLACE VIEW scope_entity_hits AS
        SELECT
            "PR ID",
            canonical_name AS entity_name,
            entity_category
        FROM scope_name_text_search_long
        WHERE canonical_name IS NOT NULL AND trim(canonical_name) != ''
    """)

    # One entity name per (doi, category); alphabetical tie-break.
    con.execute("""
        CREATE OR REPLACE VIEW doi_entity_pivot AS
        SELECT
            doi_norm,
            max(CASE WHEN category = 'journal' THEN entity_name END) AS journal,
            max(CASE WHEN category = 'institution' THEN entity_name END) AS institution,
            max(CASE WHEN category = 'publisher' THEN entity_name END) AS publisher
        FROM (
            SELECT
                doi_norm,
                lower(trim(category)) AS category,
                entity_name,
                row_number() OVER (
                    PARTITION BY doi_norm, lower(trim(category))
                    ORDER BY entity_name
                ) AS rn
            FROM doi_list_norm
            WHERE category IS NOT NULL AND trim(category) != ''
              AND entity_name IS NOT NULL AND trim(entity_name) != ''
        ) ranked
        WHERE rn = 1
        GROUP BY doi_norm
    """)


def match_doi(con):
    con.execute("""
        CREATE OR REPLACE VIEW doi_match AS
        WITH joined AS (
            SELECT
                CAST(pr."PR ID" AS VARCHAR) AS pr_id,
                dl.doi AS matched_doi,
                dl.title AS paper_title,
                dl.publication_date AS paper_date,
                pr.pub_date,
                'doi' AS match_method,
                'A' AS confidence_tier,
                1 AS is_matched,
                row_number() OVER (
                    PARTITION BY pr."PR ID"
                    ORDER BY dl.doi, dl.entity_name
                ) AS rn
            FROM pr_base pr
            JOIN doi_list_norm dl ON pr.final_doi = dl.doi_norm
            WHERE pr.final_doi IS NOT NULL AND pr.final_doi != ''
              AND pr.final_doi NOT IN ('na', 'none', 'null', 'n/a')
        )
        SELECT """ + _PAPER_COLS + """
        FROM joined WHERE rn = 1
    """)


def match_title(con):
    con.execute("""
        CREATE OR REPLACE VIEW title_match AS
        WITH joined AS (
            SELECT
                CAST(pr."PR ID" AS VARCHAR) AS pr_id,
                dl.doi AS matched_doi,
                dl.title AS paper_title,
                dl.publication_date AS paper_date,
                pr.pub_date,
                'exact_title' AS match_method,
                'C' AS confidence_tier,
                1 AS is_matched,
                row_number() OVER (
                    PARTITION BY pr."PR ID"
                    ORDER BY dl.doi, dl.entity_name
                ) AS rn
            FROM pr_base pr
            JOIN doi_list_norm dl
              ON lower(trim(pr."Article Title")) = lower(trim(dl.title))
            WHERE CAST(pr."PR ID" AS VARCHAR) NOT IN (SELECT pr_id FROM doi_match)
              AND pr."Article Title" IS NOT NULL AND trim(pr."Article Title") != ''
              AND dl.title IS NOT NULL AND trim(dl.title) != ''
        )
        SELECT """ + _PAPER_COLS + """
        FROM joined WHERE rn = 1
    """)


def match_fuzzy(con, min_score=None):
    """Build fuzzy_match view from fuzzy_title_match table (rapidfuzz)."""
    from .fuzzy_title_match import MIN_SCORE

    if min_score is None:
        min_score = MIN_SCORE

    if not _has_table(con, "fuzzy_title_match"):
        con.execute("""
            CREATE OR REPLACE VIEW fuzzy_match AS
            SELECT
                CAST(NULL AS VARCHAR) AS pr_id,
                CAST(NULL AS VARCHAR) AS matched_doi,
                CAST(NULL AS VARCHAR) AS paper_title,
                CAST(NULL AS DATE) AS paper_date,
                CAST(NULL AS DATE) AS pub_date,
                CAST(NULL AS VARCHAR) AS match_method,
                CAST(NULL AS VARCHAR) AS confidence_tier,
                CAST(NULL AS INTEGER) AS is_matched
            WHERE false
        """)
        return

    # One best fuzzy hit per PR (across all scoped entities).
    con.execute(f"""
        CREATE OR REPLACE VIEW fuzzy_match AS
        SELECT pr_id, matched_doi, paper_title, paper_date, pub_date,
               match_method, confidence_tier, is_matched
        FROM (
            SELECT
                CAST(f.pr_id AS VARCHAR) AS pr_id,
                f.matched_doi,
                f.paper_title,
                f.paper_date,
                f.pub_date,
                'fuzzy_title' AS match_method,
                'B' AS confidence_tier,
                1 AS is_matched,
                row_number() OVER (
                    PARTITION BY CAST(f.pr_id AS VARCHAR)
                    ORDER BY f.fuzzy_score DESC, f.matched_doi
                ) AS rn
            FROM fuzzy_title_match f
            WHERE f.fuzzy_score >= {float(min_score)}
              AND CAST(f.pr_id AS VARCHAR) NOT IN (SELECT pr_id FROM doi_match)
              AND CAST(f.pr_id AS VARCHAR) NOT IN (SELECT pr_id FROM title_match)
        ) ranked
        WHERE rn = 1
    """)


def scope_only(con):
    con.execute("""
        CREATE OR REPLACE VIEW scope_only AS
        SELECT
            CAST(sc."PR ID" AS VARCHAR) AS pr_id,
            CAST(NULL AS VARCHAR) AS matched_doi,
            CAST(NULL AS VARCHAR) AS paper_title,
            CAST(NULL AS DATE) AS paper_date,
            pr.pub_date,
            'scope_name_text_search' AS match_method,
            'E' AS confidence_tier,
            0 AS is_matched
        FROM scope_name_text_search sc
        JOIN pr_base pr ON pr."PR ID" = sc."PR ID"
        WHERE CAST(sc."PR ID" AS VARCHAR) NOT IN (SELECT pr_id FROM doi_match)
          AND CAST(sc."PR ID" AS VARCHAR) NOT IN (SELECT pr_id FROM title_match)
          AND CAST(sc."PR ID" AS VARCHAR) NOT IN (SELECT pr_id FROM fuzzy_match)
          AND CAST(sc."PR ID" AS VARCHAR) NOT IN (SELECT pr_id FROM embedding_match)
    """)


def _has_table(con, name):
    return con.execute("""
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
    """, [name]).fetchone()[0] > 0


def match_embedding(con, min_sim=None):
    if not _has_table(con, "embedding_title_match"):
        con.execute("""
            CREATE OR REPLACE VIEW embedding_match AS
            SELECT
                CAST(NULL AS VARCHAR) AS pr_id,
                CAST(NULL AS VARCHAR) AS matched_doi,
                CAST(NULL AS VARCHAR) AS paper_title,
                CAST(NULL AS DATE) AS paper_date,
                CAST(NULL AS DATE) AS pub_date,
                CAST(NULL AS VARCHAR) AS match_method,
                CAST(NULL AS VARCHAR) AS confidence_tier,
                CAST(NULL AS INTEGER) AS is_matched
            WHERE false
        """)
        return

    sim_filter = (
        f"AND e.embedding_sim >= {min_sim}" if min_sim is not None else ""
    )
    # One best embedding hit per PR (across all scoped entities).
    con.execute(f"""
        CREATE OR REPLACE VIEW embedding_match AS
        SELECT pr_id, matched_doi, paper_title, paper_date, pub_date,
               match_method, confidence_tier, is_matched
        FROM (
            SELECT
                CAST(e.pr_id AS VARCHAR) AS pr_id,
                e.matched_doi,
                e.paper_title,
                e.paper_date,
                e.pub_date,
                'embedding_title' AS match_method,
                'D' AS confidence_tier,
                1 AS is_matched,
                row_number() OVER (
                    PARTITION BY CAST(e.pr_id AS VARCHAR)
                    ORDER BY e.embedding_sim DESC, e.matched_doi
                ) AS rn
            FROM embedding_title_match e
            WHERE CAST(e.pr_id AS VARCHAR) NOT IN (SELECT pr_id FROM doi_match)
              AND CAST(e.pr_id AS VARCHAR) NOT IN (SELECT pr_id FROM title_match)
              AND CAST(e.pr_id AS VARCHAR) NOT IN (SELECT pr_id FROM fuzzy_match)
              {sim_filter}
        ) ranked
        WHERE rn = 1
    """)


def build_final(con):
    """Union paper matches and attach journal / institution / publisher columns."""
    con.execute("""
        CREATE OR REPLACE VIEW pr_paper_matched AS
        WITH raw AS (
            SELECT * FROM doi_match
            UNION ALL
            SELECT * FROM title_match
            UNION ALL
            SELECT * FROM fuzzy_match
            UNION ALL
            SELECT * FROM embedding_match
            UNION ALL
            SELECT * FROM scope_only
        )
        SELECT
            r.pr_id,
            r.matched_doi,
            r.paper_title,
            r.paper_date,
            r.pub_date,
            coalesce(dep.journal, sc.journal) AS journal,
            coalesce(dep.institution, sc.institution) AS institution,
            coalesce(dep.publisher, sc.publisher) AS publisher,
            r.match_method,
            r.confidence_tier,
            r.is_matched
        FROM raw r
        LEFT JOIN scope_name_text_search sc
          ON CAST(sc."PR ID" AS VARCHAR) = r.pr_id
        LEFT JOIN doi_entity_pivot dep
          ON r.matched_doi IS NOT NULL
         AND lower(trim(CAST(r.matched_doi AS VARCHAR))) = dep.doi_norm
    """)


def export_pass(con, name):
    EXPORT.mkdir(parents=True, exist_ok=True)
    path = (EXPORT / f"{name}.csv").as_posix()
    con.execute(f"COPY (SELECT * FROM {name}) TO '{path}' (HEADER, DELIMITER ',')")


def main():
    from .fuzzy_title_match import MIN_SCORE, run_fuzzy_title_match

    con = connect()
    setup_views(con)
    setup(con)
    match_doi(con)
    match_title(con)
    # Empty fuzzy view so scope/embedding exclusion clauses resolve before compute.
    match_fuzzy(con)
    match_embedding(con)
    scope_only(con)
    build_final(con)

    n_fuzzy = run_fuzzy_title_match(con)
    print(f"fuzzy_title_match: {n_fuzzy:,} rows (min_score={MIN_SCORE})")
    match_fuzzy(con)
    match_embedding(con)
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

    # Full PR rows + match_method + DOIList fields for matched papers.
    try:
        from test.export_pr_paper_matched import export_pr_paper_matched_full

        export_pr_paper_matched_full(con, out=EXPORT / "pr_paper_matched_full.csv")
    except Exception:
        # Allow running as script without package install of code/test.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "export_pr_paper_matched",
            CODE_DIR / "test" / "export_pr_paper_matched.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        mod.export_pr_paper_matched_full(con, out=EXPORT / "pr_paper_matched_full.csv")

    stats = con.execute("""
        SELECT match_method, confidence_tier, is_matched, count(*) AS n
        FROM pr_paper_matched
        GROUP BY 1, 2, 3 ORDER BY is_matched DESC, n DESC
    """).fetchall()
    print("pr_paper_matched:")
    for row in stats:
        print(f"  {row[0]:<22} tier={row[1]} matched={row[2]} n={row[3]:,}")

    fill = con.execute("""
        SELECT
            count(*) AS n_prs,
            sum(CASE WHEN journal IS NOT NULL THEN 1 ELSE 0 END) AS n_journal,
            sum(CASE WHEN institution IS NOT NULL THEN 1 ELSE 0 END) AS n_institution,
            sum(CASE WHEN publisher IS NOT NULL THEN 1 ELSE 0 END) AS n_publisher,
            sum(CASE WHEN is_matched = 1 THEN 1 ELSE 0 END) AS n_matched
        FROM pr_paper_matched
    """).fetchone()
    print(
        f"entity fill: journal={fill[1]:,}/{fill[0]:,}  "
        f"institution={fill[2]:,}/{fill[0]:,}  "
        f"publisher={fill[3]:,}/{fill[0]:,}  "
        f"paper_matched={fill[4]:,}"
    )


if __name__ == "__main__":
    main()
