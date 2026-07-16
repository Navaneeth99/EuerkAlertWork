# EurekAlert! Effectiveness Research Project

## Step 1: Create OpenAlex Crosswalk

Map journals, institutions, and publishers from the Scope of Work to OpenAlex IDs.

### Input
- `Scope of Work/Scope of Work - Saqib Mumtaz.docx`

### Process

1. **Extract entities from Scope of Work**
   - Used `textutil` to convert .docx to text
   - Manually categorized entities into: journals (17), institutions (18+), publishers (4)
   - Saved raw list to `rawdata/ListOfInstitutions.txt`

2. **Query OpenAlex API** (`code/openalex_crosswalk.py`)
   - Searched OpenAlex API endpoints:
     - `/sources` for journals
     - `/institutions` for universities/research institutes
     - `/publishers` for publishing organizations
   - Saved initial results to JSON and CSV

3. **Fix incorrect matches** (`code/fix_crosswalk.py`)
   - Corrected 3 journal matches (Intelligent Computing, Journal of Remote Sensing, Research) - original search returned wrong journals with similar names
   - Found 6 missing CAS institutes using shorter search terms
   - Matched Beijing Institute of Technology Press to university publisher entry

### Output
- `rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv` - Final crosswalk with columns:
  - `original_name`: Name from Scope of Work
  - `search_term_used`: Notes if search term was modified
  - `openalex_id`: OpenAlex ID (S=source, I=institution, P=publisher)
  - `openalex_name`: Display name in OpenAlex
  - `works_count`: Number of works
  - `issn_or_ror`: ISSN-L or ROR identifier

### Replication
```bash
# Extract text from docx
textutil -stdout -convert txt "Scope of Work/Scope of Work - Saqib Mumtaz.docx"

# Run initial crosswalk (requires: pip install requests)
python3 code/openalex_crosswalk.py

# Run corrections
python3 code/fix_crosswalk.py
```

---

## Step 2: Fetch Publications from OpenAlex

Download all publications (2015-present) for each entity in the crosswalk.

### Input
- `rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv`

### Process

1. **Run fetch script** (`code/fetch_publications.py`)
   - Reads crosswalk CSV and iterates through each entity
   - Queries OpenAlex `/works` endpoint with filters:
     - Journals: `primary_location.source.id:{id}`
     - Institutions: `authorships.institutions.id:{id}`
     - Publishers: `primary_location.source.publisher_lineage:{id}`
   - Date filter: `from_publication_date:2015-01-01`
   - Uses cursor pagination (200 works/page) for large result sets
   - Skips duplicate OpenAlex IDs (e.g., CAS Headquarters = CAS)
   - Resume capability: skips entities where output file exists

### Output
- `rawdata/PublicationData/Journals/{name}.json` - Full work objects
- `rawdata/PublicationData/Journals/{name}_dois.json` - DOI list only
- `rawdata/PublicationData/Institutions/{name}.json` - Full work objects
- `rawdata/PublicationData/Institutions/{name}_dois.json` - DOI list only
- `rawdata/PublicationData/Publishers/{name}.json` - Full work objects
- `rawdata/PublicationData/Publishers/{name}_dois.json` - DOI list only

Each JSON contains:
- `metadata`: entity info, filter used, fetch date, total works
- `works`: array of full OpenAlex work objects (or DOI summary)

### Replication
```bash
# Requires: pip install requests
# Uses email: saqib@berkeley.edu for OpenAlex polite pool

python3 code/fetch_publications.py

# Note: Large institutions (CAS ~560k works, U Tokyo ~160k) take significant time
# Script can be interrupted and resumed - skips completed entities
```

---

## Press Release Impact Dashboard (Streamlit)

Interactive dashboard comparing papers **with** vs **without** a matched EurekAlert press release (Performance, Heterogeneity, Fixed-Effects). Charts are interactive Plotly figures styled like the McKinsey report charts in `code/07_create_graphs.py`.

The app reads a **prebuilt cache** under `Processed/dashboard/` (no DuckDB/Altmetric query on startup):

- `paper_df.parquet` — slim paper-level metrics
- `overview/by_category/*.csv` — Section 1 stats for every category combination
- `coefficients/by_category/*.csv` — FE coefficients for every category combination
- `meta.json` — row counts / build timestamp / combo index

### Prerequisites (local rebuild)

1. Matching pipeline has been run so `Processed/eurekalert.duckdb` contains `embedding_title_match`, `pr_paper_matched`, and `doi_list_norm`.
2. Altmetric deliverable CSV is present at `rawdata/AltMetData/aaas_deliverable_20260415.csv`.
3. Export the dashboard cache once (or after rematching):

```bash
python code/08_export_dashboard_data.py
```

### Run locally

```bash
pip install -r requirements-dashboard.txt
streamlit run code/dashboard/app.py
```

Sidebar: category multiselect, searchable entity multiselect, and impute-zeros toggle. Overview and FE panels use precomputed category-combo caches when no entity filter is set.

### Deploy

Streamlit Community Cloud is optional. Prefer **Render** or **Hugging Face Spaces** with the repo `Dockerfile` (no local Docker required — the host builds the image).

#### Option A — Render (easiest with your existing public GitHub repo)

1. Open [render.com](https://render.com) → **New** → **Web Service**.
2. Connect GitHub and select **`Navaneeth99/EuerkAlertWork`**.
3. Settings:
   - **Language / Environment:** Docker
   - **Branch:** `main`
   - **Instance type:** Free
4. Create Web Service and wait for the build. Open the `*.onrender.com` URL.

Render uses the root [`Dockerfile`](Dockerfile), which runs `streamlit run code/dashboard/app.py` on port **8501**.

#### Option B — Hugging Face Spaces (Docker)

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Space SDK: **Docker** · create the Space.
3. In Space settings, link this GitHub repo **or** push to the Space remote:

```bash
git remote add hf https://huggingface.co/spaces/<YOUR_HF_USER>/<SPACE_NAME>
git push hf main
```

4. If the Space README is empty, paste the frontmatter from [`README_SPACE.md`](README_SPACE.md) into the Space’s `README.md`, then rebuild.

#### Option C — Local / VPS Docker

```bash
docker build -t eurekalert-dashboard .
docker run --rm -p 8501:8501 eurekalert-dashboard
```

#### Option D — Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io) → New app → repo `Navaneeth99/EuerkAlertWork`.
2. Main file: `code/dashboard/app.py` · Requirements: `requirements-dashboard.txt`.

After updating matches or metrics, rebuild the cache locally, commit `Processed/dashboard/`, and push so the host redeploys.
