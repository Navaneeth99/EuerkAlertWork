# Claude Session Handoff Note

**Project:** EurekAlert! Effectiveness Research Project
**Last Updated:** 2026-03-03

## Project Goal
Analyze effectiveness of EurekAlert! news releases on scholarly impact for organizations/publishers in Japan and China.

## Completed Steps

### Step 1: OpenAlex Crosswalk
- Extracted entities from `Scope of Work/Scope of Work - Saqib Mumtaz.docx`
- Matched to OpenAlex IDs (22 journals, 19 institutions, 4 publishers; includes 5 added SPJ control journals)
- Output: `rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv`

### Step 2: Publication Data Fetch
- Downloaded all publications (2015-present) from OpenAlex API
- 1,251,246 works, ~36GB total
- Output: `rawdata/PublicationData/{Journals,Institutions,Publishers}/*.json`
- Validated: 39/39 entities match API counts (±0.05%)

### Step 3: DOI Extraction
- Extracted 1,246,012 DOIs to single CSV (previously 1,236,741; net +9,271)
- Output: `Processed/DOIList.csv` (132.0 MB)
- Columns: entity_name, openalex_id, category, doi, publication_date

## Key Files
```
code/
  openalex_crosswalk.py      # Initial crosswalk creation
  fix_crosswalk.py           # Manual corrections
  fetch_publications.py      # Download publications (has progress bar)
  extract_dois.py            # Create DOIList.csv
  test/validate_counts.py    # Validate against API

rawdata/
  Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv
  PublicationData/{Journals,Institutions,Publishers}/*.json

Processed/
  DOIList.csv                # All DOIs in one file

tmp/
  monitor_progress.sh        # Monitor download progress
```

## Config
- OpenAlex email: saqib@berkeley.edu
- Date range: 2015-01-01 to present

## Next Steps (from Scope of Work)
- Match publications to EurekAlert! press releases
- Get Altmetric data (citations, news mentions, social media, patents, policies)
- Compare papers with/without press releases
- Analyze impact factor changes

## Notes
- CAS Headquarters = duplicate of Chinese Academy of Sciences (skipped)
- Shanghai Jiao Tong publications have no DOIs
- Largest dataset: Chinese Academy of Sciences (557k DOIs, 19GB)
- Crosswalk correction applied: Institute of Physics changed from Czech Academy to Chinese Academy of Sciences
- Added 5 control journals to the DOI output:
  - Brain Organoid and Systems Neuroscience Journal
  - Cancer Communications
  - Civil Engineering Sciences
  - Computational and Structural Biotechnology Journal
  - Computational and Structural Biotechnology Reports
