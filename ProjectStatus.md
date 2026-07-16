# Project Status Log

## About This File

This file tracks the status of the EurekAlert! Effectiveness Research Project.

**Instructions for LLMs adding updates:**
- Add new entries at the top of the Status Updates section (reverse chronological order)
- Use format: `### YYYY-MM-DD: Brief Title`
- Keep entries brief and focused on data/results (not process)
- Include: what was completed, key numbers, file locations, any issues
- Reference specific files/paths when relevant

---

## Status Updates

### 2026-06-11: Embedding Title Match & Waterfall Update

**Scope:** Entity-scoped semantic matching for in-scope PRs without a DOI link. Single mapping source: `code/scope_name_text_search.sql` (crosswalk no longer used by pipeline).

**Matching waterfall** (`code/matching_pipeline.py`):

| Pass | Method | Tier | Matched? | Count |
|------|--------|------|:--------:|------:|
| 1 | `doi` | A | yes | 14,170 |
| 2 | `exact_title` | C | yes | 235 |
| 3 | `embedding_title` | D | yes | * |
| 4 | `scope_name_text_search` | E | no | * |

Acceptance threshold: `embedding_sim >= 0.7` (`MIN_SIM` in `embedding_match.py`). Re-run `run_embedding_match(con, min_sim=0.7)` then `match_embedding(con)` to refresh counts.

**Embedding pipeline:** `code/embedding_match.py` — entity-scoped retrieval + `all-MiniLM-L6-v2` cosine similarity on PR text vs paper title; embeddings cached in `Processed/embeddings/`. Blocked fuzzy fallback: `code/title_fuzzy_match.py`.

**Key outputs:** `embedding_title_match` (DuckDB table), `code/result.csv` (review export), `Processed/pr_doi_joined/` (pipeline CSVs).

---

### 2026-05-29: PR→Paper Matching Pipeline & Entity Crosswalk

**Matching pipeline:** `code/matching_pipeline.py` — waterfall PR→paper linking against `doi_list` (2015+ universe: **376,609** PRs). Documented in `MatchingPlan.md` §3.

**Run:** `python code/matching_pipeline.py` → `Processed/pr_doi_joined/`

| Pass | Method | Tier | Paper matched? | Count |
|------|--------|------|:--------------:|------:|
| 1 | `strict_doi` | A | yes | 14,170 |
| 1b | `fulltext_doi` | A | yes | 61 |
| 2 | `exact_title` | C | yes | 107 |
| 2b | `fuzzy_title` | D | yes | 0 |
| 3 | `in_scope_heuristic` | E | no | 14,597 |

**Totals:** **14,338** confirmed PR→paper matches (`is_matched = 1`); **14,597** in-scope PRs flagged without a paper link (`is_matched = 0`); **21,452** PRs in scope overall.

**Scope detection** (before matching): org/journal → `scope_entity_guess` via merged crosswalk in `code/explore_pr_doi_join.py`:
- OpenAlex crosswalk + manual aliases (`ORG_ALIASES`, `ORG_ILIKE`)
- Curated PR mappings from `Processed/pr_entity_crosswalk.json` (**21** orgs, **43** journals active)

**Crosswalk builder:** `code/build_pr_entity_crosswalk.py` — fuzzy word-match from unique PR org/journal strings to in-scope entities. Outputs: `pr_entity_crosswalk.json`, `pr_entity_crosswalk_review.csv`. Manual rejections stored in `_rejected_*` keys (not loaded by pipeline).

**Key outputs:**

| File | Description |
|------|-------------|
| `Processed/pr_doi_joined/pr_paper_matched.csv` | Final one-row-per-PR result |
| `Processed/pr_doi_joined/pass*.csv` | Per-pass match tables |
| `Processed/pr_entity_crosswalk.json` | Curated org/journal → entity mappings |

**Notes:** Pass 2b (`rapidfuzz`, threshold 90, ±365-day date window) returns 0 matches in current run — install `rapidfuzz` and tune if needed. Pass 3 is a scoping flag only, not a confirmed paper link. Baseline naive DOI join (§2.3 of MatchingPlan) was ~18,297 PRs; pipeline applies URL normalisation, entity disambiguation, and in-scope filtering.

---

### 2026-05-27: DuckDB SQL Views for EurekAlert Analysis

**Database:** `Processed/eurekalert.duckdb` — created by `python code/eurekalert_duckdb.py setup`  
**Starter queries:** `code/eurekalert_queries.sql`  
**CLI:** `duckdb Processed/eurekalert.duckdb` then `.read code/eurekalert_queries.sql`

| View / table | Source | Rows (approx.) |
|--------------|--------|----------------|
| `press_releases` | `Processed/EurekAlert/Press_release/*.parquet` | 616,937 |
| `multimedia` | `Processed/EurekAlert/Multimedia/*.parquet` | 386,945 |
| `translations` | `Processed/EurekAlert/Translations/*.parquet` | 27,715 |
| `doi_list` | `Processed/DOIList.csv` | 1,246,012 |
| `press_releases_with_doi` | `press_releases` ⋈ `doi_list` on `DOI` | press releases with non-empty DOI |

Optional: `materialize` copies the views above into native DuckDB tables (same names) for faster repeat queries.

---

### 2026-05-27: EurekAlert Data Re-extracted to Parquet (format correction)

**Reason:** CSV output from the initial extraction was technically valid (multi-line fields properly quoted per RFC 4180) but DuckDB's `read_csv` with `ignore_errors=true` silently dropped ~400K rows due to long quoted fields containing embedded newlines. Switched to Parquet to eliminate all delimiter/quoting issues.

**Extract:** `code/extract_eurekalert.py` (pandas + openpyxl + pyarrow) re-extracted all 24 workbooks to Parquet. Each Parquet file includes `start_year` and `end_year` as columns (baked in during extraction) for fast year-range filtering in DuckDB.

| Category | Output directory | Files | Rows |
|----------|------------------|-------|------|
| Press release | `Processed/EurekAlert/Press_release/` | 24 | 616,937 |
| Multimedia | `Processed/EurekAlert/Multimedia/` | 24 | 386,945 |
| Translations | `Processed/EurekAlert/Translations/` | 24 | 27,715 |
| **Total** | | **72** | **1,031,997** |

Naming: `{category}_{start_year}_{end_year}.parquet`.

**DuckDB setup updated** (`code/eurekalert_duckdb.py`) to use `read_parquet()`. Views verified:
- `SELECT count(*) FROM press_releases` → **616,937** ✓ (matches `csv.reader` ground truth)
- `press_releases_with_doi` view joins to `Processed/DOIList.csv` on `DOI`

**Note:** Translations sparse in early years (0 rows 1997–2012); Multimedia absent 1997–2002.

---

### 2026-05-27: EurekAlert Press Release Data Extracted to CSV *(superseded — see above)*

**Input:** `rawdata/EurekAlertData/eareleases_{start_year}-{end_year}.xlsx` — 24 workbooks (1997–2002 through 2025–2025), ~1.2 GB total. Each workbook has three sheets: Press Releases, Multimedia, Translations.

**Extract:** `code/extract_eurekalert.py` (pandas + openpyxl) exports each sheet to CSV under `Processed/EurekAlert/`.

| Category | Output directory | Files | Rows (wc -l, inflated) | True rows |
|----------|------------------|-------|------------------------|-----------|
| Press release | `Processed/EurekAlert/Press_release/` | 24 | ~13.9M | 616,937 |
| Multimedia | `Processed/EurekAlert/Multimedia/` | 24 | 386,945 | 386,945 |
| Translations | `Processed/EurekAlert/Translations/` | 24 | 517,655 | 27,715 |

The high `wc -l` counts on Press_release and Translations reflect embedded newlines inside quoted `Full Text` fields — the CSVs are valid but DuckDB's CSV reader dropped rows silently. Replaced with Parquet (see entry above).

Naming: `{category}_{start_year}_{end_year}.csv` (e.g. `Press_release_2015_2015.csv`). Headers are consistent across all year files within each category.

**Press_release schema** (25 columns):

| Column | Description |
|--------|-------------|
| PR ID | EurekAlert press release identifier |
| Headline | Release headline |
| Sub-Headline | Sub-headline |
| Summary | Short summary text |
| Full Text | Full release body |
| Type | Release type |
| Category | Release category |
| Publication Date | Date published on EurekAlert |
| Organization | Posting organization name |
| Organization Types | Organization type classification |
| Org Country | Organization country |
| Primary Keyword | Primary keyword tag |
| Secondary Keywords | Secondary keyword tags |
| Translations | Linked translation indicator(s) |
| Multimedia - Images | Linked image multimedia |
| Multimedia - Video | Linked video multimedia |
| Multimedia - Audio | Linked audio multimedia |
| Conference | Associated conference |
| Journal (Matched) | Matched journal name |
| Journal (Typed) | Journal name as entered |
| DOI | Publication DOI (when provided) |
| Subject of Research | Research subject field |
| Method of Research | Research method field |
| Article Title | Linked article title |
| Public Link to Article | URL to associated article |

**Multimedia schema** (4 columns):

| Column | Description |
|--------|-------------|
| PR ID | Parent press release ID |
| Multimedia ID | Multimedia asset identifier |
| Type | Asset type (image, video, audio, etc.) |
| Title | Asset title |

**Translations schema** (7 columns):

| Column | Description |
|--------|-------------|
| PR ID | Parent press release ID |
| Translation ID | Translation record identifier |
| Language | Translation language |
| Headline | Translated headline |
| Sub-Headline | Translated sub-headline |
| Summary | Translated summary |
| Full Text | Translated full text |

**Notes:** Multimedia and Translations are sparse in early years (many year-files are header-only or near-empty). Press releases include a `DOI` column for downstream matching to `Processed/DOIList.csv` and `Processed/PaperAltMet/PaperAltMet.csv`.

---

### 2026-04-29: Altmetric Deliverable Received & Merged

**Input:** `rawdata/AltMetData/aaas_deliverable_20260415.csv` (181 MB, 1,246,222 rows) + data dictionary. Covers 7 mention sources: policy, patent, news, Facebook, X, Bluesky, YouTube. Includes `altmetric_id` and details-page URL.

**Merge:** `code/merge_altmetric.R` (R + data.table) joins deliverable to `Processed/DOIList.csv` by DOI.
- Output: `Processed/PaperAltMet/PaperAltMet.csv` (188 MB, 1,246,012 rows) + `coverage_by_entity.csv`
- **Join is 100%** — every DOI we sent came back.
- **44.74%** of DOIs have an `altmetric_id` (Altmetric has a record for them).
- **37.42%** have ≥ 1 mention across any source.

**Coverage highlights:**
- Journals: mostly 70–100% (Civil Eng. Sciences 100%, Intelligent Computing 99%, Research 94%); laggards: Comp. & Struct. Biotech *Reports* 21%, J. EMDR 35%.
- Institutions: cluster 35–52% (U Tokyo 52%, CAS 43%, Aerospace Info Inst. CAS 24%).
- Publishers: low (Higher Ed Press 34%, Tsinghua UP 28%, **Beijing Inst. of Tech Press 0/106**).

**Mention totals across all rows:** X 4.25M (32% of papers), news 523k (6.2%), patents 149k (5.3%), Bluesky 112k (2.0%), Facebook 79k (3.8%), policy 20k (0.8%), video 9k (0.4%).

---

### 2026-03-03: Crosswalk Corrections & DOI List Regenerated

**Step 1: Crosswalk Updated** (`rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv`)
- Now 45 entities: 22 journals, 20 institutions, 4 publishers (was 40 entities, 17 journals)
- Three changes applied per client feedback:
  1. **Institution correction:** "Institute of Physics of the Czech Academy of Sciences" → "Institute of Physics, Chinese Academy of Sciences" (OpenAlex `I4210159876`, ROR `05cvf7v30`, Beijing, China)
  2. **Publisher URL added:** Shanghai Jiao Tong University Journal Center — added website `https://www.qk.sjtu.edu.cn/EN/column/column22.shtml`
  3. **5 new SPJ control journals added** (with OpenAlex IDs looked up by ISSN)

**Step 2: Publication Data Fetched for 6 new/changed entities**
- Institute of Physics, Chinese Academy of Sciences: 17,454 works
- Brain Organoid and Systems Neuroscience Journal: 47 works
- Cancer Communications: 978 works
- Civil Engineering Sciences: 11 works
- Computational and Structural Biotechnology Journal: 3,466 works
- Computational and Structural Biotechnology Reports: 75 works

**Step 3: DOI List Regenerated**
- Total DOIs: **1,246,012** (previously 1,236,741; net **+9,271**)
- Output: `Processed/DOIList.csv` (132.0 MB)

| Change | Old DOIs | New DOIs | Net |
|--------|----------|----------|-----|
| Inst. of Physics: Czech → Chinese | 12,729 | 17,423 | +4,694 |
| 5 new SPJ journals | 0 | 4,577 | +4,577 |
| **Total** | | | **+9,271** |

**Updated DOIs by Entity:**

*Institutions (20):*
Chinese Academy of Sciences: 557,137 | University of Tokyo: 158,515 | Univ. of Science & Tech of China: 117,964 | University of Kyoto: 108,191 | Nagoya University: 64,426 | Hokkaido University: 57,903 | Shenzhen Inst. of Advanced Tech: 21,109 | IGSNRR CAS: 19,330 | Inst. of Physics, Chinese Academy: 17,423 | Dalian Inst. of Chemical Physics: 16,819 | Inst. of Atmospheric Physics: 12,317 | Aerospace Information Research Inst.: 12,284 | Osaka City University: 11,570 | Hefei Institutes of Physical Science: 10,242 | Inst. of Process Engineering: 10,142 | Osaka Prefecture University: 9,535 | Osaka Metropolitan University: 7,433 | Changchun Inst. of Optics: 6,864

*Publishers (4):*
Higher Education Press: 12,389 | Tsinghua University Press: 3,934 | Beijing Institute of Technology Press: 106 | Shanghai Jiao Tong Univ. Journal Center: 0

*Journals (22):*
Comp. & Structural Biotech Journal: 3,466 | Research: 1,699 | Cancer Communications: 978 | Biomaterials Research: 754 | Ecosystem Health and Sustainability: 548 | Plant Phenomics: 424 | Journal of EMDR Practice and Research: 339 | Space: Science & Technology: 278 | Cyborg and Bionic Systems: 252 | Energy Material Advances: 243 | Journal of Bio-X Research: 218 | Journal of Remote Sensing: 194 | BMEF (BME Frontiers): 150 | Ultrafast Science: 136 | Intelligent Computing: 129 | BioDesign Research: 125 | Health Data Science: 114 | Ocean-Land-Atmosphere Research: 101 | Advanced Devices & Instrumentation: 98 | Comp. & Structural Biotech Reports: 75 | Brain Organoid & Systems Neuroscience: 47 | Civil Engineering Sciences: 11

---

### 2024-12-18: DOI Extraction Complete

**Step 3: DOI List Extracted**
- Total DOIs: **1,236,741**
- Output: `Processed/DOIList.csv` (130.9 MB)
- Columns: entity_name, openalex_id, category, doi, publication_date

**DOIs by Entity (descending order):**

*Institutions:*
Chinese Academy of Sciences: 557,137 | University of Tokyo: 158,515 | Univ. of Science & Tech of China: 117,964 | University of Kyoto: 108,191 | Nagoya University: 64,426 | Hokkaido University: 57,903 | Shenzhen Inst. of Advanced Tech: 21,109 | IGSNRR CAS: 19,330 | Dalian Inst. of Chemical Physics: 16,819 | Inst. of Physics, Czech Academy: 12,729 | Inst. of Atmospheric Physics: 12,317 | Aerospace Information Research Inst.: 12,284 | Osaka City University: 11,570 | Hefei Institutes of Physical Science: 10,242 | Inst. of Process Engineering: 10,142 | Osaka Prefecture University: 9,535 | Osaka Metropolitan University: 7,433 | Changchun Inst. of Optics: 6,864

*Publishers:*
Higher Education Press: 12,389 | Tsinghua University Press: 3,934 | Beijing Institute of Technology Press: 106 | Shanghai Jiao Tong Univ. Journal Center: 0

*Journals:*
Research: 1,699 | Biomaterials Research: 754 | Ecosystem Health and Sustainability: 548 | Plant Phenomics: 424 | Journal of EMDR Practice and Research: 339 | Space: Science & Technology: 278 | Cyborg and Bionic Systems: 252 | Energy Material Advances: 243 | Journal of Bio-X Research: 218 | Journal of Remote Sensing: 194 | BMEF (BME Frontiers): 150 | Ultrafast Science: 136 | Intelligent Computing: 129 | BioDesign Research: 125 | Health Data Science: 114 | Ocean-Land-Atmosphere Research: 101 | Advanced Devices & Instrumentation: 98

**Notes:** CAS Headquarters excluded (duplicate). Shanghai Jiao Tong publications had no DOIs.

---

### 2024-12-18: Data Collection Complete

**Step 1: OpenAlex Crosswalk**
- Mapped 40 entities from Scope of Work to OpenAlex IDs
- 17 journals, 20 institutions, 4 publishers (1 duplicate institution skipped)
- Output: `rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv`

**Step 2: Publication Data Fetched**
- Date range: 2015-01-01 to present
- Total works downloaded: **1,251,246**
- Storage: ~36GB

| Category | Count | Works |
|----------|-------|-------|
| Journals | 17 | 5,803 |
| Institutions | 19 | 1,228,211 |
| Publishers | 4 | 17,232 |

- Output: `rawdata/PublicationData/{Journals,Institutions,Publishers}/`
- Each entity has full JSON + DOI-only JSON

**Validation**
- 39/39 entities validated against live OpenAlex API
- Difference: +674 works (0.05%) - confirmed as new publications added after fetch
- All differences positive (API ≥ Local), no data loss

**Largest Files:**
- Chinese Academy of Sciences: 19GB (560,623 works)
- University of Tokyo: 6.2GB (161,663 works)
- Kyoto University: 3.5GB (110,372 works)
