-- Starter queries for EurekAlert DuckDB analysis
-- Run: python code/eurekalert_duckdb.py setup
-- Then: python code/eurekalert_duckdb.py sql "$(cat code/eurekalert_queries.sql | head -20)"
-- Or use DuckDB CLI: duckdb Processed/eurekalert.duckdb

--- Show all tables in the database
-- SHOW TABLES;

-- -- Of the matches press releases, check the number of records where the organisation name match the entity name in the DOI list
-- SELECT count(*) AS n
-- FROM press_releases pr
-- INNER JOIN doi_list dl ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
-- WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != ''
-- AND pr."Organization" = dl.entity_name;

-- SELECT pr."PR ID", pr."Organization", dl.entity_name AS "Entity Name", dl.doi AS "DOI"
-- FROM press_releases pr
-- INNER JOIN doi_list dl ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
-- WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != ''
-- AND pr."Organization" != dl.entity_name
-- limit 10;

-- -- Of the matches press releases, check the number of records where the journal name match the journal name in the DOI list


-- select * from doi_list limit 10;
-- Column fill rate for press_releases_from_2015
-- Filled = non-null and non-blank after trim
-- WITH total AS (
--     SELECT count(*)::BIGINT AS total_rows
    -- FROM press_releases_from_2015
-- ),
-- fills AS (
    -- SELECT 'start_year' AS column_name,
        --    count(*) FILTER (WHERE start_year IS NOT NULL AND length(trim(cast(start_year AS VARCHAR))) > 0) AS filled_rows
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'end_year',
        --    count(*) FILTER (WHERE end_year IS NOT NULL AND length(trim(cast(end_year AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'PR ID',
        --    count(*) FILTER (WHERE "PR ID" IS NOT NULL AND length(trim(cast("PR ID" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Headline',
        --    count(*) FILTER (WHERE "Headline" IS NOT NULL AND length(trim(cast("Headline" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Sub-Headline',
        --    count(*) FILTER (WHERE "Sub-Headline" IS NOT NULL AND length(trim(cast("Sub-Headline" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Summary',
        --    count(*) FILTER (WHERE "Summary" IS NOT NULL AND length(trim(cast("Summary" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Full Text',
        --    count(*) FILTER (WHERE "Full Text" IS NOT NULL AND length(trim(cast("Full Text" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Type',
        --    count(*) FILTER (WHERE "Type" IS NOT NULL AND length(trim(cast("Type" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Category',
        --    count(*) FILTER (WHERE "Category" IS NOT NULL AND length(trim(cast("Category" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Publication Date',
        --    count(*) FILTER (WHERE "Publication Date" IS NOT NULL AND length(trim(cast("Publication Date" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Organization',
        --    count(*) FILTER (WHERE "Organization" IS NOT NULL AND length(trim(cast("Organization" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Organization Types',
        --    count(*) FILTER (WHERE "Organization Types" IS NOT NULL AND length(trim(cast("Organization Types" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Org Country',
        --    count(*) FILTER (WHERE "Org Country" IS NOT NULL AND length(trim(cast("Org Country" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Primary Keyword',
        --    count(*) FILTER (WHERE "Primary Keyword" IS NOT NULL AND length(trim(cast("Primary Keyword" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Secondary Keywords',
        --    count(*) FILTER (WHERE "Secondary Keywords" IS NOT NULL AND length(trim(cast("Secondary Keywords" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Translations',
        --    count(*) FILTER (WHERE "Translations" IS NOT NULL AND length(trim(cast("Translations" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Multimedia - Images',
        --    count(*) FILTER (WHERE "Multimedia - Images" IS NOT NULL AND length(trim(cast("Multimedia - Images" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Multimedia - Video',
        --    count(*) FILTER (WHERE "Multimedia - Video" IS NOT NULL AND length(trim(cast("Multimedia - Video" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Multimedia - Audio',
        --    count(*) FILTER (WHERE "Multimedia - Audio" IS NOT NULL AND length(trim(cast("Multimedia - Audio" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Conference',
        --    count(*) FILTER (WHERE "Conference" IS NOT NULL AND length(trim(cast("Conference" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Journal (Matched)',
        --    count(*) FILTER (WHERE "Journal (Matched)" IS NOT NULL AND length(trim(cast("Journal (Matched)" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Journal (Typed)',
        --    count(*) FILTER (WHERE "Journal (Typed)" IS NOT NULL AND length(trim(cast("Journal (Typed)" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'DOI',
        --    count(*) FILTER (WHERE "DOI" IS NOT NULL AND length(trim(cast("DOI" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Subject of Research',
        --    count(*) FILTER (WHERE "Subject of Research" IS NOT NULL AND length(trim(cast("Subject of Research" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Method of Research',
        --    count(*) FILTER (WHERE "Method of Research" IS NOT NULL AND length(trim(cast("Method of Research" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Article Title',
        --    count(*) FILTER (WHERE "Article Title" IS NOT NULL AND length(trim(cast("Article Title" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
    -- UNION ALL
    -- SELECT 'Public Link to Article',
        --    count(*) FILTER (WHERE "Public Link to Article" IS NOT NULL AND length(trim(cast("Public Link to Article" AS VARCHAR))) > 0)
    -- FROM press_releases_from_2015
-- )
-- SELECT
    -- f.column_name,
    -- t.total_rows,
    -- f.filled_rows,
    -- t.total_rows - f.filled_rows AS empty_rows,
    -- round(100.0 * f.filled_rows / t.total_rows, 2) AS fill_rate_pct
-- FROM fills f
-- CROSS JOIN total t
-- ORDER BY fill_rate_pct DESC, f.column_name;

-- Multimedia linked to press releases (2015+)
-- SELECT m."Type", count(*) AS n
-- FROM multimedia m
-- WHERE m.start_year >= 2015
-- GROUP BY 1
-- ORDER BY n DESC;

-- Translation languages (where data exists)
-- SELECT "Language", count(*) AS n
-- FROM translations
-- WHERE "Language" IS NOT NULL
-- GROUP BY 1
-- ORDER BY n DESC
-- LIMIT 15;

-- -- Match press-release DOIs to OpenAlex DOI list (requires DOIList.csv)
-- SELECT
--     count(DISTINCT pr."PR ID") AS matched_pr,
--     count(DISTINCT dl.doi) AS matched_dois
-- FROM press_releases pr
-- INNER JOIN doi_list dl ON lower(trim(pr."DOI")) = lower(trim(dl.doi))
-- WHERE pr."DOI" IS NOT NULL AND trim(pr."DOI") != '';

-- -- Sample headlines with DOI for spot-checking
-- SELECT  "DOI", "Publication Date", "Organization"
-- FROM press_releases
-- WHERE "DOI" IS NOT NULL AND trim("DOI") != ''
-- LIMIT 10;


-- Top journals in DOI_list (2015+) by row count
SELECT
    entity_name,
    COUNT(*) AS n
FROM doi_list
WHERE "publication_date" >= '2015-01-01'
  AND category = 'journal'
GROUP BY 1
ORDER BY n DESC
LIMIT 20;

-- Top journals in press_releases (2015+) by row count
SELECT
    coalesce("Journal (Matched)", "Journal (Typed)") AS journal,
    COUNT(*) AS n
FROM press_releases_from_2015
WHERE (("Journal (Matched)" IS NOT NULL AND trim("Journal (Matched)") != '')
       OR ("Journal (Typed)" IS NOT NULL AND trim("Journal (Typed)") != ''))
GROUP BY 1
ORDER BY n DESC
LIMIT 20;

-- -- Most common publication dates in press_releases (2015+)
-- SELECT
--     "Publication Date",
--     COUNT(*) AS n
-- FROM press_releases_from_2015
-- WHERE "Publication Date" >= '2015-01-01'
-- GROUP BY 1
-- ORDER BY n DESC
-- LIMIT 20;

-- Left join the top 20 journals in DOI_list (with count of dois) to all the distinct journals in press_releases (2015+)
select * from (
(SELECT
    dl.entity_name AS journal,
    count(*) as n
FROM doi_list dl
WHERE dl.category = 'journal'
GROUP BY 1) dr 
LEFT JOIN (SELECT DISTINCT coalesce("Journal (Matched)", "Journal (Typed)") as press_release_journal FROM press_releases_from_2015) pr
    ON lower(trim(dr.journal)) = lower(trim(pr.press_release_journal))
) order by n desc;



select * from (
(SELECT
    dl.entity_name AS institution,
    count(*) as n
FROM doi_list dl
WHERE dl.category = 'institution'
GROUP BY 1) dr 
LEFT JOIN (SELECT DISTINCT organization as press_release_institution FROM press_releases_from_2015) pr
    ON lower(trim(dr.institution)) = lower(trim(pr.press_release_institution))
) order by n desc;


-- select the count of records by category in doi_list
SELECT category, count(*) as n FROM doi_list GROUP BY 1 ORDER BY n DESC;


-- Count of DOI list records that can be matched to press releases (2015+) via DOI (LEFT JOIN doi_list → press_releases)
SELECT
    COUNT(*) AS n_matched
FROM doi_list dl
LEFT JOIN press_releases_from_2015 pr
    ON lower(trim(dl.doi)) = lower(trim(pr.DOI))
WHERE pr.DOI IS NOT NULL
  AND trim(pr.DOI) != '';

select doi from doi_list order by doi desc limit 10;

select doi from press_releases_from_2015 where DOI is not null and trim(DOI) != '' order by DOI desc limit 10;

-- Check if DOI is in 10.xxxx/yyyy format
SELECT
    doi,
    CASE
        WHEN trim(doi) != ''
             AND lower(doi) NOT IN ('na', 'none', 'null', 'n/a')
             AND regexp_matches(trim(doi), '^10\.\S+/\S+$')
        THEN 1
        ELSE 0
    END AS is_valid_doi
FROM doi_list
ORDER BY is_valid_doi DESC, doi limit 10;

-- Select the count of DOI list records that are in 10.xxxx/yyyy format and ones are not in the format
SELECT
    COUNT(case when trim(doi) != ''
  AND lower(doi) NOT IN ('na', 'none', 'null', 'n/a') AND regexp_matches(trim(doi), '^10\.\S+/\S+$')then 1 end) AS n_valid_dois,
    COUNT(*) AS n_total
FROM doi_list;

-- Select the count of press releases (2015+) that have a DOI in 10.xxxx/yyyy format and ones are not in the format
SELECT
    COUNT(case when trim(DOI) != ''
  AND lower(DOI) NOT IN ('na', 'none', 'null', 'n/a') AND regexp_matches(trim(doi), '^10\.\S+/\S+$')then 1 end) AS n_valid_dois,
    COUNT(*) AS n_total
FROM press_releases_from_2015;

-- Show some invalid DOIs from press_releases_from_2015
SELECT
    DOI
FROM press_releases_from_2015
WHERE
    trim(DOI) != ''
    AND lower(DOI) NOT IN ('na', 'none', 'null', 'n/a')
    AND NOT regexp_matches(trim(DOI), '^10\.\S+/\S+$')
    order by random()
LIMIT 20;

-- Example: Show DOIs in press_releases_from_2015 that have a "https://doi.org/" prefix, and how to clean them to match extract_dois.py (strip prefix)
SELECT
    DOI AS original_doi,
    CASE
        WHEN DOI LIKE 'https://doi.org/%' THEN substr(DOI, 17)
        ELSE DOI
    END AS cleaned_doi
FROM press_releases_from_2015
WHERE DOI LIKE 'https://doi.org/%'
  AND DOI IS NOT NULL
  AND trim(DOI) != ''
LIMIT 20;

-- Example: Count how many DOIs in press_releases_from_2015 have the https://doi.org/ prefix
SELECT
    COUNT(*) AS n_with_prefix
FROM press_releases_from_2015
WHERE DOI LIKE 'https://doi.org/%'
  AND DOI IS NOT NULL
  AND trim(DOI) != '';

-- Example: Create a view correcting DOI format in press_releases_from_2015 to match the cleaning logic in extract_dois.py
CREATE OR REPLACE VIEW press_releases_from_2015_cleaned_doi AS
SELECT
    *,
    CASE WHEN regexp_replace(DOI, ' ', '') LIKE 'https://doi.org/%' THEN substr(DOI, 17) 
         WHEN regexp_replace(DOI, ' ', '') LIKE 'doi.org/%' THEN substr(DOI, 10)
         WHEN regexp_replace(DOI, ' ', '') LIKE 'DOI:%' THEN substr(DOI, 5)
         ELSE regexp_replace(DOI, ' ', '') END AS cleaned_doi
FROM press_releases_from_2015;

-- Select the count of press releases (2015+) that have a DOI in 10.xxxx/yyyy format and ones are not in the format
SELECT
    COUNT(case when trim(cleaned_doi) != ''
  AND lower(cleaned_doi) NOT IN ('na', 'none', 'null', 'n/a') AND regexp_matches(trim(cleaned_doi), '^10\.\S+/\S+$')then 1 end) AS n_valid_dois,
    COUNT(*) AS n_total
FROM press_releases_from_2015_cleaned_doi
where cleaned_doi is not null and trim(cleaned_doi) != '';

-- Show some invalid DOIs from press_releases_from_2015_cleaned_doi
SELECT
    cleaned_doi
FROM press_releases_from_2015_cleaned_doi
WHERE
    trim(cleaned_doi) != ''
    AND lower(cleaned_doi) NOT IN ('na', 'none', 'null', 'n/a')
    AND NOT regexp_matches(trim(cleaned_doi), '^10\.\S+/\S+$')
    order by random()
LIMIT 50;

-- Do an inner join of the press_releases_from_2015_cleaned_doi table to the doi_list table on the cleaned_doi column
SELECT
    count(*) as n
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN doi_list dl ON lower(trim(pr.cleaned_doi)) = lower(trim(dl.doi))
WHERE pr.cleaned_doi IS NOT NULL AND trim(pr.cleaned_doi) != '';
-- 18354

describe press_releases_from_2015_cleaned_doi;
describe doi_list;
-- Do an inner join of the press_releases_from_2015_cleaned_doi table to the doi_list table on the title column
SELECT
    count(*) as n
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN doi_list dl ON lower(trim(pr."Article Title")) = lower(trim(dl.title))
WHERE pr."Article Title" IS NOT NULL AND trim(pr."Article Title") != '';


-- Unique PRs matched by DOI
SELECT count(DISTINCT pr."PR ID") AS n
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN doi_list dl ON lower(trim(pr.cleaned_doi)) = lower(trim(dl.doi))
WHERE pr.cleaned_doi IS NOT NULL AND trim(pr.cleaned_doi) != '';

SELECT
    count(*), count(distinct pr."PR ID") as n
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN (select distinct doi from doi_list) dl ON lower(trim(pr.cleaned_doi)) = lower(trim(dl.doi))
WHERE pr.cleaned_doi IS NOT NULL AND trim(pr.cleaned_doi) != '';


-- Unique PRs matched by title  
SELECT count(DISTINCT pr."PR ID") AS n
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN (select distinct title from doi_list) dl ON lower(trim(pr."Article Title")) = lower(trim(dl.title))
WHERE pr."Article Title" IS NOT NULL AND trim(pr."Article Title") != '';

-- Do an inner join of the press_releases_from_2015_cleaned_doi table to the doi_list table on the title column and union inner join on doi column
select count(*) as n from (
SELECT 
    pr."PR ID" 
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN (select distinct doi from doi_list) dl ON lower(trim(pr.cleaned_doi)) = lower(trim(dl.doi))
WHERE pr.cleaned_doi IS NOT NULL AND trim(pr.cleaned_doi) != ''
UNION
SELECT 
    pr."PR ID"
FROM press_releases_from_2015_cleaned_doi pr
INNER JOIN (select distinct title from doi_list) dl ON lower(trim(pr."Article Title")) = lower(trim(dl.title))
WHERE pr."Article Title" IS NOT NULL AND trim(pr."Article Title") != ''
) as a;