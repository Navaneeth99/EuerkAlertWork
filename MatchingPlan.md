# Press Release → Paper Matching Plan

## 1. Scope and Goal

The goal is to link each EurekAlert press release (2015–present) to a paper in `doi_list`, which contains **1,246,012 DOIs** for ~45 entities in scope (Chinese/Japanese institutions, specific journals, and publishers).

Only press releases with `Publication Date >= 2015-01-01` are in scope. This yields **376,609 press releases** as the working universe.

---

## 2. Current Coverage: DOI Exact-Match

The simplest approach — matching `press_releases.DOI` directly against `doi_list.doi` — is already implemented via the `press_releases_with_doi` view.

### 2.1 Press Release Universe (2015+)

| Metric | Count |
|--------|------:|
| Total press releases (2015+) | 376,609 |
| With a non-empty DOI field | 206,124 (54.7%) |
| Without any DOI | 170,485 (45.3%) |

DOI availability has improved over time — from ~10% in 2015 to ~73% by 2025.

| Year | Total PRs | With DOI | % |
|------|----------:|---------:|--:|
| 2015 | 29,259 | 2,822 | 9.6% |
| 2016 | 30,619 | 11,531 | 37.7% |
| 2017 | 34,829 | 14,123 | 40.6% |
| 2018 | 33,952 | 16,336 | 48.1% |
| 2019 | 34,618 | 18,682 | 54.0% |
| 2020 | 35,581 | 21,803 | 61.3% |
| 2021 | 36,362 | 23,495 | 64.6% |
| 2022 | 34,142 | 22,684 | 66.4% |
| 2023 | 34,067 | 22,573 | 66.3% |
| 2024 | 35,505 | 24,407 | 68.7% |
| 2025 | 37,675 | 27,668 | 73.4% |

### 2.2 Column Fill Rates (`press_releases_with_pub_date_2015`)

Fill rate = share of rows where the value is non-null and non-blank after `trim`. Total rows: **376,609**. Query: `code/eurekalert_queries.sql`.

| Column | Filled | Empty | Fill rate |
|--------|-------:|------:|----------:|
| Headline | 376,608 | 1 | 100.00% |
| Multimedia - Audio | 376,609 | 0 | 100.00% |
| Multimedia - Images | 376,609 | 0 | 100.00% |
| Multimedia - Video | 376,609 | 0 | 100.00% |
| Org Country | 376,600 | 9 | 100.00% |
| Organization | 376,600 | 9 | 100.00% |
| Organization Types | 376,600 | 9 | 100.00% |
| PR ID | 376,609 | 0 | 100.00% |
| Publication Date | 376,609 | 0 | 100.00% |
| Type | 376,609 | 0 | 100.00% |
| end_year | 376,609 | 0 | 100.00% |
| start_year | 376,609 | 0 | 100.00% |
| Primary Keyword | 374,227 | 2,382 | 99.37% |
| Category | 368,454 | 8,155 | 97.83% |
| Full Text | 365,470 | 11,139 | 97.04% |
| Summary | 364,504 | 12,105 | 96.79% |
| Secondary Keywords | 339,913 | 36,696 | 90.26% |
| Journal (Matched) | 269,251 | 107,358 | 71.49% |
| **DOI** | **206,124** | **170,485** | **54.73%** |
| Sub-Headline | 176,648 | 199,961 | 46.90% |
| **Article Title** | **106,279** | **270,330** | **28.22%** |
| Subject of Research | 63,486 | 313,123 | 16.86% |
| Method of Research | 62,431 | 314,178 | 16.58% |
| Journal (Typed) | 23,549 | 353,060 | 6.25% |
| Translations | 21,993 | 354,616 | 5.84% |
| Conference | 19,469 | 357,140 | 5.17% |
| Public Link to Article | 0 | 376,609 | 0.00% |

**Implications for matching:** `DOI` (54.7%) is the primary join key; `Article Title` (28.2%) is the main fallback for Pass 2. `Public Link to Article` is entirely empty in this slice and cannot be used. `Journal (Matched)` (71.5%) may help with Pass 3 scoping.

### 2.3 DOI Match Results

| Metric | Count |
|--------|------:|
| Press releases (2015+) matched by DOI | **18,297** |
| Distinct DOIs matched | **13,173** |
| Press releases with DOI but unmatched | 191,986 |
| Distinct unmatched DOIs in PRs | 181,724 |
| doi_list DOIs not seen in any 2015+ PR | 1,057,003 |

### 2.4 Why Coverage Is Low

The low match rate is primarily **a scope issue, not a data quality issue.**

- `doi_list` contains only papers from ~45 specific entities (Chinese Academy of Sciences, University of Tokyo, specific SPJ journals, etc.)
- The vast majority of EurekAlert press releases come from other global institutions (e.g., ETH Zurich, University of Kansas, Massachusetts General Hospital) that are not in scope
- Of the 191,986 unmatched PRs with DOIs, most are from out-of-scope organisations — these should not be expected to match

**Of the 1,246,012 papers in `doi_list`, about 13,173 (~1.1%) have had a press release on EurekAlert.** This is the true hit-rate for the research question.

### 2.5 Matched Press Releases by Entity (Top 20)

| Entity | Category | Matched PRs |
|--------|----------|------------:|
| Chinese Academy of Sciences | institution | 5,655 |
| University of Tokyo | institution | 3,035 |
| University of Kyoto | institution | 1,713 |
| Univ. of Science & Tech of China | institution | 1,376 |
| Nagoya University | institution | 1,193 |
| Hokkaido University | institution | 1,031 |
| Higher Education Press | publisher | 611 |
| Inst. of Atmospheric Physics, CAS | institution | 529 |
| Dalian Inst. of Chemical Physics, CAS | institution | 337 |
| Osaka Metropolitan University | institution | 314 |
| Shenzhen Inst. of Advanced Tech, CAS | institution | 302 |
| Inst. of Physics, CAS | institution | 277 |
| Hefei Inst. of Physical Science, CAS | institution | 267 |
| Osaka City University | institution | 185 |
| Tsinghua University Press | publisher | 173 |
| Research | journal | 135 |
| IGSNRR CAS | institution | 123 |
| Plant Phenomics | journal | 121 |
| Journal of Remote Sensing | journal | 115 |
| Osaka Prefecture University | institution | 111 |

---
#### Note on Publication Dates

It is important to note that publication dates in both the press release dataset and the paper metadata (`doi_list`) are often inconsistent, even in cases where the DOI matches exactly. The difference between the press release publication date and the article publication date can vary substantially — from being published on the same day, to having gaps of several months (or even dates where the press release precedes the official article publication). This variability means that publication date cannot be reliably used as a strong matching signal and must be interpreted with caution in downstream analyses or interpretation of match timing.

## 3. Matching Algorithm

Implemented in `code/matching_pipeline.py`. Run with:

```bash
python code/matching_pipeline.py
```

Outputs are written to `Processed/pr_doi_joined/` (one CSV per pass plus `pr_paper_matched.csv`).

### 3.1 Overview

Matching is a **waterfall**: each pass runs only on press releases not already matched by a higher-priority pass. The first hit wins.

```
┌─────────────────────────────────────────────────────────────────┐
│  Setup: scope detection (org + journal → entity_name)           │
└────────────────────────────┬────────────────────────────────────┘
                             │
  Pass 1   strict_doi         │  Tier A  is_matched=1  PR DOI field → doi_list
  Pass 1b  fulltext_doi       │  Tier A  is_matched=1  DOI regex in Full Text + Summary
  Pass 2   exact_title       │  Tier C  is_matched=1  Article Title = paper title (in-scope only)
  Pass 2b  fuzzy_title        │  Tier D  is_matched=1  Entity-scoped fuzzy title (in-scope only)
  Pass 3   in_scope_heuristic │  Tier E  is_matched=0  In-scope flag only — no paper linked
                             │
                             ▼
                    pr_paper_matched (one row per PR)
```

**Latest run (2026-05):**

| Pass | Method | Tier | Matched? | Count |
|------|--------|------|----------|------:|
| 1 | `strict_doi` | A | yes | 14,170 |
| 1b | `fulltext_doi` | A | yes | 61 |
| 2 | `exact_title` | C | yes | 107 |
| 2b | `fuzzy_title` | D | yes | 0* |
| 3 | `in_scope_heuristic` | E | no | 14,118 |

\*Pass 2b requires `rapidfuzz`; when installed and tuned, it adds entity-scoped fuzzy matches.

**Confirmed paper matches:** ~14,338 PRs (`is_matched = 1`).  
**In-scope but unmatched:** ~14,118 PRs flagged for review (`is_matched = 0`).

---

### 3.2 Scope Detection (Pre-Pass Setup)

Before matching, each press release is annotated with a `scope_entity_guess` and checked for in-scope status. This drives entity disambiguation when a DOI maps to multiple entities, and restricts title-based passes to relevant candidates.

**Universe:** `press_releases_with_pub_date_2015` (376,609 PRs with `Publication Date >= 2015-01-01`).

#### Organisation mapping

Press release `Organization` → `entity_name` via a merged org crosswalk built from:

1. **OpenAlex crosswalk** (`rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv`) — canonical entity names and OpenAlex aliases
2. **Manual aliases** (`ORG_ALIASES` in `code/explore_pr_doi_join.py`) — known EurekAlert naming variants (e.g. `Kyoto University` → `University of Kyoto`)
3. **PR entity crosswalk** (`Processed/pr_entity_crosswalk.json`) — curated mappings from unique PR organisation strings to in-scope entities (source: `pr_entity_crosswalk`)
4. **ILIKE patterns** (`ORG_ILIKE`) — substring fallbacks for CAS institutes, Japanese universities, etc.

Exact match on `lower(trim(Organization))`.

#### Journal mapping

Press release `Journal (Matched)` / `Journal (Typed)` → `entity_name` via:

1. **PR entity crosswalk** — exact journal name mappings from `Processed/pr_entity_crosswalk.json`
2. **Scope entity list** — substring / exact match against in-scope journal entities from the OpenAlex crosswalk

Rejected mappings are stored in `_rejected_organizations` / `_rejected_journals` in the JSON file and are **not** loaded.

#### scope_entity_guess

Resolved in priority order:

```
COALESCE(
  org_crosswalk match,
  ORG_ILIKE pattern match,
  journal_crosswalk match on Journal (Matched),
  journal_crosswalk match on Journal (Typed)
)
```

#### pr_in_scope

A press release is **in-scope** if either:

- `scope_entity_guess IS NOT NULL`, or
- its `PR ID` appears in `pr_journal_scope` (journal name matches an in-scope entity)

Title-based passes (2, 2b) and Pass 3 operate on `pr_in_scope` only. DOI passes (1, 1b) run on all PRs in `pr_with_scope` (including out-of-scope PRs whose DOI happens to be in `doi_list`).

---

### 3.3 DOI Normalisation

All DOI joins use a normalised form: `lower(trim(doi))`.

**Pass 1 — PR DOI field cleaning** strips common URL prefixes before matching:

| Input format | Normalised to |
|--------------|---------------|
| `https://doi.org/10.xxxx` | `10.xxxx` |
| `http://doi.org/10.xxxx` | `10.xxxx` |
| `doi.org/10.xxxx` | `10.xxxx` |
| `DOI: 10.xxxx` | `10.xxxx` |
| bare `10.xxxx` | unchanged |

Placeholder values (`na`, `none`, `null`, `n/a`) are excluded.

**Pass 1b — Full-text extraction** applies a regex to `Full Text` + `Summary`:

```
(10\.\d{4,9}/[-._;()/:A-Z0-9]+)
```

Used only when Pass 1 did not match and no usable DOI is in the DOI field.

---

### 3.4 Multi-Entity DOI Disambiguation

When one DOI maps to multiple `doi_list` rows (different entities), the best row is chosen by `match_rank`:

| Rank | Condition |
|------|-----------|
| 1 | `doi_list.entity_name = pr.scope_entity_guess` |
| 2 | `doi_list.category = 'journal'` |
| 3 | `doi_list.category = 'publisher'` |
| 4 | all other categories |

Within the same rank, `entity_name` ascending breaks ties. One row per PR (`row_number() … rn = 1`).

---

### 3.5 Pass Details

#### Pass 1 — `strict_doi` (Tier A)

- **Input:** `pr_with_scope`, `cleaned_doi`
- **Join:** `cleaned_doi` (normalised) = `doi_list.doi_norm`
- **Skip if:** DOI empty or placeholder

#### Pass 1b — `fulltext_doi` (Tier A)

- **Input:** PRs not matched in Pass 1
- **Join:** DOI extracted from `Full Text` + `Summary` = `doi_list.doi_norm`
- **Skip if:** Pass 1 already matched

#### Pass 2 — `exact_title` (Tier C)

- **Input:** `pr_in_scope`, not matched in Pass 1/1b
- **Join:** `lower(trim(Article Title)) = lower(trim(doi_list.title))`
- **Disambiguation:** same `match_rank` as DOI passes

#### Pass 2b — `fuzzy_title` (Tier D)

- **Input:** `pr_in_scope` with non-empty `Article Title` and non-null `scope_entity_guess`, not matched in Pass 1/1b/2
- **Candidates:** papers in `doi_list` where `entity_name = scope_entity_guess`
- **Scorer:** `rapidfuzz.fuzz.token_sort_ratio`
- **Threshold:** ≥ 90 (`FUZZY_THRESHOLD`)
- **Date filter:** if PR has `pub_date`, prefer papers within ±365 days (`DATE_WINDOW_DAYS`); fall back to full entity pool if none in window
- **Requires:** `rapidfuzz` in `requirements.txt`

#### Pass 3 — `in_scope_heuristic` (Tier E)

- **Input:** `pr_in_scope`, not matched in any prior pass
- **Output:** `scope_entity_guess` as `entity_name`; `matched_doi`, `paper_title`, `paper_date` are NULL
- **Purpose:** flags PRs likely belonging to an in-scope entity without confirming a specific paper
- **`is_matched = 0`** — not counted as a confirmed PR→paper link

---

### 3.6 Final Output — `pr_paper_matched`

All passes are stacked and deduplicated by `pass_priority` (lowest wins):

| Priority | Pass | `is_matched` |
|---------:|------|:------------:|
| 1 | `strict_doi` | 1 |
| 2 | `fulltext_doi` | 1 |
| 3 | `exact_title` | 1 |
| 4 | `fuzzy_title` | 1 |
| 5 | `in_scope_heuristic` | 0 |

**Columns:** `pr_id`, `matched_doi`, `entity_name`, `paper_title`, `paper_date`, `pub_date`, `scope_entity_guess`, `match_method`, `confidence_tier`, `is_matched`

---

### 3.7 Entity Crosswalk Maintenance

PR-specific org/journal mappings are built and reviewed separately:

```bash
python code/build_pr_entity_crosswalk.py [--min-score 90]
```

| Output | Description |
|--------|-------------|
| `Processed/pr_entity_crosswalk.json` | Active mappings (`organizations`, `journals`) plus `_rejected_*` audit trail |
| `Processed/pr_entity_crosswalk_review.csv` | Review spreadsheet |

Scoring uses weighted word-to-word matching (`rapidfuzz`) with generic-word filtering. Manual curation moves false positives to `_rejected_*`. The matching pipeline loads only `organizations` and `journals`.

---

### 3.8 Future Improvements

| Idea | Rationale |
|------|-----------|
| BM25 / embedding retrieval within entity | Better recall when PR headline ≠ paper title |
| Cross-encoder reranking | Reduce false positives from fuzzy title pass |
| NER / author overlap | Booster signals after deterministic passes |
| Tighter date validation | Publication dates are inconsistent (see note in §2); use cautiously as a hard filter only |

---

## 4. Data Gaps and Known Issues

| Issue | Impact | Mitigation |
|-------|--------|------------|
| 160,432 PRs (2015+) have no DOI and no Article Title | Cannot be matched automatically | Pass 3 in-scope flag; manual review for high-value entities |
| doi_list covers only ~45 entities; most EurekAlert PRs are out-of-scope | Most unmatched PRs are expected | Scope detection via org/journal crosswalk before reporting "unmatched" |
| Pre-2016 DOI coverage is sparse (< 10% in 2015) | Underestimates 2015 impact | Flag 2015 as low-confidence year |
| Publication dates inconsistent between PR and paper | Cannot use date as a hard match signal | Optional ±365-day filter in Pass 2b only; see §2 note |
| PR entity crosswalk requires manual curation | False positives if auto-accepted blindly | Review via `_rejected_*` sections; rebuild with `build_pr_entity_crosswalk.py` |

---

## 5. Implementation Status

| Step | Action | Status | Output |
|------|--------|--------|--------|
| 1 | DOI URL normalisation + full-text DOI extraction | **Done** | Pass 1 / Pass 1b |
| 2 | Organisation + journal crosswalk | **Done** | `Processed/pr_entity_crosswalk.json`, `explore_pr_doi_join.py` |
| 3 | Paper titles in DuckDB (`doi_list.title`) | **Done** | Used by Pass 2 / 2b |
| 4 | Waterfall matching pipeline | **Done** | `code/matching_pipeline.py` → `Processed/pr_doi_joined/` |
| 5 | Entity-scoped fuzzy title match | **Done** (needs `rapidfuzz`) | Pass 2b |
| 6 | In-scope heuristic for unmatched PRs | **Done** | Pass 3 (`is_matched = 0`) |
| 7 | Embedding / reranking passes | Planned | See §3.8 |

---

## 6. Key Files

| File | Description |
|------|-------------|
| `Processed/eurekalert.duckdb` | DuckDB database with views |
| `Processed/DOIList.csv` | 1,246,012 in-scope paper DOIs |
| `Processed/EurekAlert/Press_release/*.parquet` | 616,937 press releases (all years) |
| `Processed/pr_entity_crosswalk.json` | Curated PR org/journal → entity mappings |
| `Processed/pr_doi_joined/pr_paper_matched.csv` | Final waterfall match output |
| `rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv` | Canonical entity crosswalk |
| `rawdata/PublicationData/` | Full OpenAlex JSON per entity (contains `title`) |
| `code/matching_pipeline.py` | Waterfall matching pipeline (Pass 1–3) |
| `code/build_pr_entity_crosswalk.py` | Build/review PR entity crosswalk |
| `code/explore_pr_doi_join.py` | Scope setup, org/journal crosswalk helpers, join diagnostics |
| `code/eurekalert_duckdb.py` | DuckDB view setup and query helper |
| `code/eurekalert_queries.sql` | Coverage queries |
