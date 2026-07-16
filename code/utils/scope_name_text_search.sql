-- Single source of truth for PR -> doi_list entity_name mapping.
-- canonical_name must match doi_list.entity_name exactly.
-- Requires: pr_base view (matching_pipeline.setup)
-- OpenAlex alternate titles come from openalex_alternate_titles.json
-- (path placeholder {{OPENALEX_ALTERNATE_TITLES_JSON}} is filled by matching_pipeline.setup).
-- OpenAlex alts shorter than 5 chars are dropped (BIT/ADI/… false-positives).
-- Chinese Academy of Sciences is aliased to … Headquarters to match DOIList.
-- manual_variations: only near-identical name forms (&/and, Tech, Univ, hyphens,
--   known acronyms). Do NOT map to different journals/orgs.
CREATE OR REPLACE TABLE scope_name_text_search AS
WITH manual_variations AS (
  SELECT * FROM (VALUES
  ('journal', 'Advanced Devices & Instrumentation', 'Advanced Devices & Instrumentation'),
  ('journal', 'Advanced Devices & Instrumentation', 'Advanced Devices and Instrumentation'),
  ('journal', 'Advanced Devices & Instrumentation', 'Adv Devices Instrum'),
  ('journal', 'Energy Material Advances', 'Energy Material Advances'),
  ('journal', 'Energy Material Advances', 'Energy Materials Advances'),
  ('journal', 'Energy Material Advances', 'Energy Material Adv'),
  ('journal', 'Space: Science & Technology', 'Space: Science & Technology'),
  ('journal', 'Space: Science & Technology', 'Space: Science and Technology'),
  ('journal', 'Space: Science & Technology', 'Space Science & Technology'),
  ('journal', 'Space: Science & Technology', 'Space Science and Technology'),
  ('journal', 'Space: Science & Technology', 'Space：Science & Technology'),
  ('journal', 'Space: Science & Technology', 'Space Sci Technol'),
  ('journal', 'Cyborg and Bionic Systems', 'Cyborg and Bionic Systems'),
  ('journal', 'Cyborg and Bionic Systems', 'Cyborg & Bionic Systems'),
  ('journal', 'Cyborg and Bionic Systems', 'Cyborg Bionic Systems'),
  ('journal', 'BioDesign Research', 'BioDesign Research'),
  ('journal', 'BioDesign Research', 'Bio-Design Research'),
  ('journal', 'BioDesign Research', 'Bio Design Research'),
  ('journal', 'BioDesign Research', 'BioDesign Res'),
  ('journal', 'Biomaterials Research', 'Biomaterials Research'),
  ('journal', 'Biomaterials Research', 'Biomaterials Res'),
  ('journal', 'BMEF (BME Frontiers)', 'BMEF (BME Frontiers)'),
  ('journal', 'BMEF (BME Frontiers)', 'BME Frontiers'),
  ('journal', 'Ecosystem Health and Sustainability', 'Ecosystem Health and Sustainability'),
  ('journal', 'Ecosystem Health and Sustainability', 'Ecosystem Health & Sustainability'),
  ('journal', 'Ecosystem Health and Sustainability', 'Ecosystem Health Sustain'),
  ('journal', 'Health Data Science', 'Health Data Science'),
  ('journal', 'Health Data Science', 'Health Data Sci'),
  ('journal', 'Intelligent Computing', 'Intelligent Computing'),
  ('journal', 'Intelligent Computing', 'Intelligent Comput'),
  ('journal', 'Intelligent Computing', 'Intell Computing'),
  ('journal', 'Journal of Bio-X Research', 'Journal of Bio-X Research'),
  ('journal', 'Journal of Bio-X Research', 'Journal of Bio X Research'),
  ('journal', 'Journal of Bio-X Research', 'J Bio-X Res'),
  ('journal', 'Journal of Remote Sensing', 'Journal of Remote Sensing'),
  ('journal', 'Journal of Remote Sensing', 'J Remote Sens'),
  ('journal', 'Ocean-Land-Atmosphere Research (OLAR)', 'Ocean-Land-Atmosphere Research (OLAR)'),
  ('journal', 'Ocean-Land-Atmosphere Research (OLAR)', 'Ocean-Land-Atmosphere Research'),
  ('journal', 'Ocean-Land-Atmosphere Research (OLAR)', 'Ocean Land Atmosphere Research'),
  ('journal', 'Ocean-Land-Atmosphere Research (OLAR)', 'Ocean-Land-Atmosphere Res'),
  ('journal', 'Plant Phenomics', 'Plant Phenomics'),
  ('journal', 'Plant Phenomics', 'Plant Phenomics journal'),
  -- Journal title "Research" is a common English word; never search bare "Research".
  ('journal', 'Research', 'Res (Wash D C)'),
  ('journal', 'Research', 'Science Partner Journal Research'),
  ('journal', 'Ultrafast Science', 'Ultrafast Science'),
  ('journal', 'Ultrafast Science', 'Ultrafast Sci'),
  ('journal', 'Journal of EMDR Practice and Research', 'Journal of EMDR Practice and Research'),
  ('journal', 'Journal of EMDR Practice and Research', 'Journal of EMDR Practice & Research'),
  ('journal', 'Journal of EMDR Practice and Research', 'J EMDR Pract Res'),
  ('journal', 'Journal of EMDR Practice and Research', 'EMDR Practice and Research'),
  ('journal', 'Cancer Communications', 'Cancer Communications'),
  ('journal', 'Computational and Structural Biotechnology Journal', 'Computational and Structural Biotechnology Journal'),
  ('institution', 'Science Partner Journals', 'Science Partner Journals'),
  ('institution', 'Science Partner Journals', 'Science Partner Journal'),
  ('institution', 'Science Partner Journals', 'Science Partner Journals (SPJ)'),
  ('institution', 'Science Partner Journals', 'AAAS Science Partner Journals'),
  ('institution', 'Beijing Institute of Technology Press Co., Ltd', 'Beijing Institute of Technology Press Co., Ltd'),
  ('institution', 'Beijing Institute of Technology Press Co., Ltd', 'Beijing Institute of Technology Press Co Ltd'),
  ('institution', 'Beijing Institute of Technology Press Co., Ltd', 'Beijing Institute of Technology Press'),
  ('institution', 'Beijing Institute of Technology Press Co., Ltd', 'Beijing Inst of Technology Press'),
  ('institution', 'Beijing Institute of Technology Press Co., Ltd', 'BIT Press'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'Chinese Academy of Sciences Headquarters'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'Chinese Academy of Sciences'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'Chinese Academy of Sciences (CAS)'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'The Chinese Academy of Sciences'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'Chinese Academy of Science'),
  ('institution', 'Chinese Academy of Sciences Headquarters', 'CAS Headquarters'),
  ('institution', 'University of Science and Technology of China', 'University of Science and Technology of China'),
  ('institution', 'University of Science and Technology of China', 'Univ. of Science and Technology of China'),
  ('institution', 'University of Science and Technology of China', 'Univ of Sci and Tech of China'),
  ('institution', 'Institute of Physics, Chinese Academy of Sciences', 'Institute of Physics, Chinese Academy of Sciences'),
  ('institution', 'Institute of Physics, Chinese Academy of Sciences', 'Institute of Physics, CAS'),
  ('institution', 'Institute of Physics, Chinese Academy of Sciences', 'Institute of Physics CAS'),
  ('institution', 'Institute of Physics, Chinese Academy of Sciences', 'IOP CAS'),
  ('institution', 'Institute of Process Engineering, Chinese Academy of Sciences', 'Institute of Process Engineering, Chinese Academy of Sciences'),
  ('institution', 'Institute of Process Engineering, Chinese Academy of Sciences', 'Institute of Process Engineering CAS'),
  ('institution', 'Institute of Process Engineering, Chinese Academy of Sciences', 'IPE-CAS'),
  ('institution', 'Institute of Process Engineering, Chinese Academy of Sciences', 'IPE CAS'),
  ('institution', 'IGSNRR CAS', 'IGSNRR CAS'),
  ('institution', 'IGSNRR CAS', 'IGSNRR'),
  ('institution', 'IGSNRR CAS', 'Institute of Geographic Sciences and Natural Resources Research, CAS'),
  ('institution', 'IGSNRR CAS', 'Institute of Geographic Sciences and Natural Resources Research CAS'),
  ('institution', 'IGSNRR CAS', 'Institute of Geographic Sciences and Natural Resources Research'),
  ('institution', 'Institute of Atmospheric Physics, Chinese Academy of Sciences', 'Institute of Atmospheric Physics, Chinese Academy of Sciences'),
  ('institution', 'Institute of Atmospheric Physics, Chinese Academy of Sciences', 'Institute of Atmospheric Physics CAS'),
  ('institution', 'Institute of Atmospheric Physics, Chinese Academy of Sciences', 'IAP-CAS'),
  ('institution', 'Institute of Atmospheric Physics, Chinese Academy of Sciences', 'IAP CAS'),
  ('institution', 'Aerospace Information Research Institute, Chinese Academy of Sciences', 'Aerospace Information Research Institute, Chinese Academy of Sciences'),
  ('institution', 'Aerospace Information Research Institute, Chinese Academy of Sciences', 'Aerospace Information Research Institute CAS'),
  ('institution', 'Aerospace Information Research Institute, Chinese Academy of Sciences', 'Aerospace Information Research Institute'),
  ('institution', 'Aerospace Information Research Institute, Chinese Academy of Sciences', 'AIRI CAS'),
  ('institution', 'Aerospace Information Research Institute, Chinese Academy of Sciences', 'AIR CAS'),
  ('institution', 'Dalian Institute of Chemical Physics, Chinese Academy Sciences', 'Dalian Institute of Chemical Physics, Chinese Academy Sciences'),
  ('institution', 'Dalian Institute of Chemical Physics, Chinese Academy Sciences', 'Dalian Institute of Chemical Physics, Chinese Academy of Sciences'),
  ('institution', 'Dalian Institute of Chemical Physics, Chinese Academy Sciences', 'Dalian Institute of Chemical Physics'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'Changchun Institute of Optics, Fine Mechanics And Physics'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'Changchun Institute of Optics, Fine Mechanics and Physics'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'Changchun Institute of Optics Fine Mechanics and Physics CAS'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'Light Publishing Center CIOMP'),
  ('institution', 'Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS', 'CIOMP'),
  ('institution', 'Hefei Institutes of Physical Science, Chinese Academy of Sciences', 'Hefei Institutes of Physical Science, Chinese Academy of Sciences'),
  ('institution', 'Hefei Institutes of Physical Science, Chinese Academy of Sciences', 'Hefei Institutes of Physical Science CAS'),
  ('institution', 'Hefei Institutes of Physical Science, Chinese Academy of Sciences', 'Hefei Institutes of Physical Science'),
  ('institution', 'Hefei Institutes of Physical Science, Chinese Academy of Sciences', 'HFIPS CAS'),
  ('institution', 'Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences', 'Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences'),
  ('institution', 'Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences', 'Shenzhen Institute of Advanced Technology'),
  ('institution', 'Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences', 'Shenzhen Institutes of Advanced Technology'),
  ('institution', 'Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences', 'SIAT CAS'),
  ('institution', 'Higher Education Press', 'Higher Education Press'),
  ('institution', 'Higher Education Press', 'Higher Ed Press'),
  ('institution', 'Tsinghua University Press', 'Tsinghua University Press'),
  ('institution', 'Tsinghua University Press', 'Tsinghua Univ. Press'),
  ('institution', 'Tsinghua University Press', 'Tsinghua Univ Press'),
  ('institution', 'Shanghai Jiao Tong University Journal Center', 'Shanghai Jiao Tong University Journal Center'),
  ('institution', 'Shanghai Jiao Tong University Journal Center', 'Shanghai Jiao Tong University Journal Centre'),
  ('institution', 'Shanghai Jiao Tong University Journal Center', 'Shanghai Jiao Tong Univ Journal Center'),
  ('institution', 'Shanghai Jiao Tong University Journal Center', 'SJTU Journal Center'),
  ('institution', 'Nagoya University', 'Nagoya University'),
  ('institution', 'Nagoya University', 'Nagoya Univ'),
  ('institution', 'Nagoya University', 'Univ Nagoya'),
  ('institution', 'Nagoya University', 'Univ. Nagoya'),
  ('institution', 'Hokkaido University', 'Hokkaido University'),
  ('institution', 'Hokkaido University', 'Hokkaido Univ'),
  ('institution', 'Hokkaido University', 'Univ Hokkaido'),
  ('institution', 'Hokkaido University', 'Univ. Hokkaido'),
  ('institution', 'University of Tokyo', 'University of Tokyo'),
  ('institution', 'University of Tokyo', 'The University of Tokyo'),
  ('institution', 'University of Tokyo', 'Tokyo University'),
  ('institution', 'University of Tokyo', 'UTokyo'),
  ('institution', 'University of Tokyo', 'U Tokyo'),
  ('institution', 'University of Tokyo', 'Uni. Tokyo'),
  ('institution', 'University of Kyoto', 'University of Kyoto'),
  ('institution', 'University of Kyoto', 'Kyoto University'),
  ('institution', 'University of Kyoto', 'Kyoto Univ'),
  ('institution', 'University of Kyoto', 'Univ. Kyoto'),
  ('institution', 'University of Kyoto', 'Uni. Kyoto'),
  ('institution', 'Osaka Metropolitan University', 'Osaka Metropolitan University'),
  ('institution', 'Osaka Metropolitan University', 'Osaka Metropolitan Univ'),
  ('institution', 'Osaka Metropolitan University', 'Osaka Met Univ'),
  ('institution', 'Osaka City University', 'Osaka City University'),
  ('institution', 'Osaka City University', 'Osaka City Univ'),
  ('institution', 'Osaka Prefecture University', 'Osaka Prefecture University'),
  ('institution', 'Osaka Prefecture University', 'Osaka Prefecture Univ')
  ) AS t(entity_category, canonical_name, search_name)
),
-- Drop short OpenAlex alts (e.g. BIT, ADI, HDS) — they false-positive via ILIKE '%…%'.
-- Alias OpenAlex original_name onto DOIList entity_name where they diverge.
openalex_alternate_variations AS (
  SELECT
    category AS entity_category,
    CASE trim(original_name)
      WHEN 'Chinese Academy of Sciences'
        THEN 'Chinese Academy of Sciences Headquarters'
      ELSE trim(original_name)
    END AS canonical_name,
    trim(CAST(alt AS VARCHAR)) AS search_name
  FROM read_json(
    '{{OPENALEX_ALTERNATE_TITLES_JSON}}',
    format = 'array',
    auto_detect = true
  ) AS t,
  unnest(t.alternate_titles) AS u(alt)
  WHERE alt IS NOT NULL
    AND length(trim(CAST(alt AS VARCHAR))) >= 5
),
name_variations AS (
  SELECT entity_category, canonical_name, search_name FROM manual_variations
  UNION
  SELECT entity_category, canonical_name, search_name FROM openalex_alternate_variations
),
-- Block ultra-generic tokens that explode under ILIKE '%…%' (e.g. Research → 300k+ PRs).
name_variations_safe AS (
  SELECT entity_category, canonical_name, search_name
  FROM name_variations
  WHERE lower(trim(search_name)) NOT IN (
    'research', 'science', 'press', 'journal', 'university', 'institute',
    'communications', 'reports', 'advances', 'systems', 'technology'
  )
),
matches AS (
  SELECT
    pr."PR ID",
    nv.canonical_name,
    nv.search_name,
    case when coalesce(pr."Full Text", '') ILIKE '%' || nv.search_name || '%' then 1 else 0 end as matched_in_full_text_flag,
    case when coalesce(pr."Summary", '') ILIKE '%' || nv.search_name || '%' then 1 else 0 end as matched_in_summary_flag,
    case when coalesce(pr."Organization", '') ILIKE '%' || nv.search_name || '%' then 1 else 0 end as matched_in_organization_flag,
    case when coalesce(pr."Journal (Matched)", '') ILIKE '%' || nv.search_name || '%' then 1 else 0 end as matched_in_journal_matched_flag,
    case when coalesce(pr."Journal (Typed)", '') ILIKE '%' || nv.search_name || '%' then 1 else 0 end as matched_in_journal_typed_flag
  FROM pr_base pr
  inner JOIN name_variations_safe nv
    ON coalesce(pr."Full Text", '') ILIKE '%' || nv.search_name || '%'
    OR coalesce(pr."Summary", '') ILIKE '%' || nv.search_name || '%'
    OR coalesce(pr."Organization", '') ILIKE '%' || nv.search_name || '%'
    OR coalesce(pr."Journal (Matched)", '') ILIKE '%' || nv.search_name || '%'
    OR coalesce(pr."Journal (Typed)", '') ILIKE '%' || nv.search_name || '%'
)
select "PR ID", canonical_name, search_name,
 matched_in_organization_flag,
 matched_in_journal_typed_flag,
 matched_in_journal_matched_flag,
 matched_in_summary_flag,
 matched_in_full_text_flag from
(select "PR ID", canonical_name, search_name,
 matched_in_organization_flag,
 matched_in_journal_typed_flag,
 matched_in_journal_matched_flag,
 matched_in_summary_flag,
 matched_in_full_text_flag,row_number() over
(partition by "PR ID" order by
matched_in_organization_flag desc,
matched_in_journal_matched_flag desc,
matched_in_journal_typed_flag desc,
matched_in_summary_flag desc,
matched_in_full_text_flag desc,
length(search_name) desc) as rn from matches) as m where rn = 1;

SELECT count(*), count(distinct "PR ID") from scope_name_text_search;
-- Summary: which names appear and how often
SELECT
  canonical_name,
  search_name,
  count(DISTINCT "PR ID") AS pr_count
FROM scope_name_text_search
GROUP BY 1, 2
ORDER BY pr_count DESC;
