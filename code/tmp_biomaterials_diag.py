"""Diagnose Biomaterials Research low match rate."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
JOINED = ROOT / "Processed" / "pr_doi_joined"

con = duckdb.connect()

con.execute(f"""
CREATE TABLE ppm AS
SELECT * FROM read_csv_auto('{(JOINED / "pr_paper_matched.csv").as_posix()}', header=true);
CREATE TABLE scope AS
SELECT * FROM read_csv_auto('{(JOINED / "scope_only.csv").as_posix()}', header=true);
CREATE TABLE doi_m AS
SELECT * FROM read_csv_auto('{(JOINED / "doi_match.csv").as_posix()}', header=true);
CREATE TABLE full AS
SELECT * FROM read_csv_auto('{(JOINED / "pr_paper_matched_full.csv").as_posix()}', header=true);
""")

print("=== Overall Biomaterials Research ===")
print(
    con.sql(
        """
        SELECT entity_name, count(*) n, sum(is_matched) matched,
               round(sum(is_matched)*1.0/count(*), 4) pct
        FROM ppm WHERE entity_name = 'Biomaterials Research'
        GROUP BY 1
        """
    )
    .df()
    .to_string(index=False)
)

print("\n=== By match_method ===")
print(
    con.sql(
        """
        SELECT match_method, confidence_tier, is_matched, count(*) n
        FROM ppm WHERE entity_name = 'Biomaterials Research'
        GROUP BY 1,2,3 ORDER BY n DESC
        """
    )
    .df()
    .to_string(index=False)
)

# Inspect full CSV columns
cols = con.sql("DESCRIBE full").df()
print("\n=== full columns ===")
print(cols["column_name"].tolist())

# Journal / org for unmatched vs matched
print("\n=== Top Journal (Matched) among Biomaterials Research rows ===")
print(
    con.sql(
        """
        SELECT coalesce("Journal (Matched)", '(null)') AS jmatched,
               coalesce("Journal (Typed)", '(null)') AS jtyped,
               is_matched, count(*) n
        FROM full
        WHERE entity_name = 'Biomaterials Research'
        GROUP BY 1,2,3
        ORDER BY n DESC
        LIMIT 40
        """
    )
    .df()
    .to_string(index=False)
)

print("\n=== Top Organization among unmatched Biomaterials Research ===")
print(
    con.sql(
        """
        SELECT coalesce(Organization, '(null)') AS org, count(*) n
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 0
        GROUP BY 1 ORDER BY n DESC LIMIT 25
        """
    )
    .df()
    .to_string(index=False)
)

print("\n=== Matched sample (is_matched=1) ===")
print(
    con.sql(
        """
        SELECT pr_id, match_method, matched_doi,
               left(coalesce("Article Title",''), 80) AS article_title,
               left(coalesce("Journal (Matched)",''), 60) AS jmatched,
               left(coalesce(Organization,''), 50) AS org
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 1
        LIMIT 25
        """
    )
    .df()
    .to_string(index=False)
)

print("\n=== Unmatched sample (is_matched=0) ===")
print(
    con.sql(
        """
        SELECT pr_id, match_method,
               left(coalesce("Article Title",''), 80) AS article_title,
               left(coalesce("Journal (Matched)",''), 60) AS jmatched,
               left(coalesce("Journal (Typed)",''), 40) AS jtyped,
               left(coalesce(Organization,''), 50) AS org,
               left(coalesce(DOI,''), 50) AS doi
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 0
        ORDER BY pr_id
        LIMIT 30
        """
    )
    .df()
    .to_string(index=False)
)

# How many unmatched have journal literally Biomaterials Research vs Biomaterials*
print("\n=== Unmatched journal name patterns ===")
print(
    con.sql(
        """
        SELECT
          CASE
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials research%' THEN 'jmatched: Biomaterials Research'
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials science%' THEN 'jmatched: Biomaterials Science'
            WHEN lower(coalesce("Journal (Matched)",'')) = 'biomaterials' THEN 'jmatched: Biomaterials (exact)'
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials%' THEN 'jmatched: other Biomaterials*'
            WHEN lower(coalesce("Journal (Typed)",'')) LIKE '%biomaterials research%' THEN 'jtyped: Biomaterials Research'
            WHEN lower(coalesce("Journal (Typed)",'')) LIKE '%biomaterials%' THEN 'jtyped: Biomaterials*'
            WHEN lower(coalesce(Organization,'')) LIKE '%biomaterials%' THEN 'org has Biomaterials'
            ELSE 'no Biomaterials in journal/org fields'
          END AS bucket,
          count(*) n
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 0
        GROUP BY 1 ORDER BY n DESC
        """
    )
    .df()
    .to_string(index=False)
)

print("\n=== Matched journal name patterns ===")
print(
    con.sql(
        """
        SELECT
          CASE
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials research%' THEN 'jmatched: Biomaterials Research'
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials science%' THEN 'jmatched: Biomaterials Science'
            WHEN lower(coalesce("Journal (Matched)",'')) = 'biomaterials' THEN 'jmatched: Biomaterials (exact)'
            WHEN lower(coalesce("Journal (Matched)",'')) LIKE '%biomaterials%' THEN 'jmatched: other Biomaterials*'
            WHEN lower(coalesce("Journal (Typed)",'')) LIKE '%biomaterials research%' THEN 'jtyped: Biomaterials Research'
            WHEN lower(coalesce("Journal (Typed)",'')) LIKE '%biomaterials%' THEN 'jtyped: Biomaterials*'
            WHEN lower(coalesce(Organization,'')) LIKE '%biomaterials%' THEN 'org has Biomaterials'
            ELSE 'no Biomaterials in journal/org fields'
          END AS bucket,
          count(*) n
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 1
        GROUP BY 1 ORDER BY n DESC
        """
    )
    .df()
    .to_string(index=False)
)

# DOI list size
print("\n=== DOIList Biomaterials Research paper count ===")
doi_csv = ROOT / "Processed" / "DOIList.csv"
con.execute(
    f"""
    CREATE TABLE doi_list AS
    SELECT * FROM read_csv_auto('{doi_csv.as_posix()}', header=true);
    """
)
print(
    con.sql(
        """
        SELECT entity_name, count(*) n, count(DISTINCT doi) ndoi
        FROM doi_list WHERE entity_name = 'Biomaterials Research'
        GROUP BY 1
        """
    )
    .df()
    .to_string(index=False)
)

# Among unmatched with a DOI, how many DOIs are in doi_list at all?
print("\n=== Unmatched PRs with DOI present vs in doi_list ===")
print(
    con.sql(
        """
        WITH u AS (
          SELECT pr_id, DOI,
            lower(trim(
              CASE
                WHEN regexp_replace(coalesce(DOI,''), ' ', '') ILIKE 'https://doi.org/%'
                  THEN substr(regexp_replace(DOI, ' ', ''), 17)
                WHEN regexp_replace(coalesce(DOI,''), ' ', '') ILIKE 'http://doi.org/%'
                  THEN substr(regexp_replace(DOI, ' ', ''), 16)
                WHEN regexp_replace(coalesce(DOI,''), ' ', '') ILIKE 'doi.org/%'
                  THEN substr(regexp_replace(DOI, ' ', ''), 9)
                ELSE NULLIF(trim(regexp_replace(coalesce(DOI,''), ' ', '')), '')
              END
            )) AS doi_norm
          FROM full
          WHERE entity_name = 'Biomaterials Research' AND is_matched = 0
        )
        SELECT
          count(*) AS unmatched,
          sum(CASE WHEN doi_norm IS NOT NULL AND doi_norm != '' THEN 1 ELSE 0 END) AS has_doi,
          sum(CASE WHEN d.doi IS NOT NULL THEN 1 ELSE 0 END) AS doi_in_any_doi_list,
          sum(CASE WHEN d.entity_name = 'Biomaterials Research' THEN 1 ELSE 0 END) AS doi_in_biomaterials_research
        FROM u
        LEFT JOIN (
          SELECT lower(trim(doi)) AS doi, entity_name,
                 row_number() OVER (PARTITION BY lower(trim(doi)) ORDER BY entity_name) rn
          FROM doi_list
        ) d ON u.doi_norm = d.doi AND d.rn = 1
        """
    )
    .df()
    .to_string(index=False)
)

# Sample unmatched journals that are clearly wrong journals
print("\n=== Top wrong Journal (Matched) values (unmatched) ===")
print(
    con.sql(
        """
        SELECT coalesce("Journal (Matched)", '(empty)') AS j, count(*) n
        FROM full
        WHERE entity_name = 'Biomaterials Research' AND is_matched = 0
        GROUP BY 1 ORDER BY n DESC LIMIT 30
        """
    )
    .df()
    .to_string(index=False)
)
)
