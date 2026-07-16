---
title: EurekAlert Press Release Impact
emoji: 📰
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: With-PR vs without-PR Altmetric and citation impact dashboard
---

# EurekAlert Press Release Impact Dashboard

Streamlit dashboard comparing papers with vs without a matched EurekAlert press release.

This Space builds from the repository `Dockerfile` (Docker SDK). Runtime data is the prebuilt cache under `Processed/dashboard/` — no DuckDB required.

## Local Docker

```bash
docker build -t eurekalert-dashboard .
docker run --rm -p 8501:8501 eurekalert-dashboard
```

Open http://localhost:8501
