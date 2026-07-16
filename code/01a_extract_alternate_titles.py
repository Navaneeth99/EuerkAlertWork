"""Extract alternate titles/names from OpenAlex for crosswalk entities.

Reads OpenAlex IDs from openalex_crosswalk_clean.csv and fetches each entity
from the API. Journals/publishers use alternate_titles; institutions use
display_name_alternatives.

Usage:
  python code/01a_extract_alternate_titles.py
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

EMAIL = os.environ.get("OPENALEX_EMAIL", "navaneethbiju@gmail.com")
API_KEY = os.environ.get("OPENALEX_API")
BASE_URL = "https://api.openalex.org"
RATE_LIMIT_DELAY = 0.1

CROSSWALK_PATH = (
    PROJECT_DIR
    / "rawdata"
    / "Institution_OpenAlexCrossWalk"
    / "openalex_crosswalk_clean.csv"
)
OUT_DIR = PROJECT_DIR / "rawdata" / "Institution_OpenAlexCrossWalk"
OUT_CSV = OUT_DIR / "openalex_alternate_titles.csv"
OUT_JSON = OUT_DIR / "openalex_alternate_titles.json"

CATEGORY_TO_ENDPOINT = {
    "journal": "sources",
    "institution": "institutions",
    "publisher": "publishers",
}

# Align OpenAlex original_name with DOIList.entity_name (exact string).
ENTITY_NAME_ALIASES = {
    "Chinese Academy of Sciences": "Chinese Academy of Sciences Headquarters",
}

# Short alts (BIT, ADI, HDS, …) false-positive heavily under ILIKE '%name%'.
MIN_ALTERNATE_TITLE_LEN = 5


def short_id(openalex_id: str) -> str:
    """https://openalex.org/S123 → S123"""
    return openalex_id.rstrip("/").rsplit("/", 1)[-1]


def load_crosswalk(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            oid = (row.get("openalex_id") or "").strip()
            if not oid:
                continue
            rows.append(row)
    return rows


def fetch_entity(category: str, openalex_id: str) -> dict | None:
    endpoint = CATEGORY_TO_ENDPOINT.get(category.lower())
    if not endpoint:
        print(f"  Unknown category '{category}', skipping")
        return None

    url = f"{BASE_URL}/{endpoint}/{short_id(openalex_id)}"
    params = {"mailto": EMAIL}
    if API_KEY:
        params["api_key"] = API_KEY

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"  Error fetching {openalex_id}: {e}")
        return None


def canonicalize_entity_name(name: str) -> str:
    name = (name or "").strip()
    return ENTITY_NAME_ALIASES.get(name, name)


def alternate_names(category: str, entity: dict) -> list[str]:
    if category.lower() == "institution":
        alts = entity.get("display_name_alternatives") or []
    else:
        alts = entity.get("alternate_titles") or []
    # Keep order, drop empties/duplicates/short false-positive alts
    seen = set()
    out = []
    for name in alts:
        name = (name or "").strip()
        if not name or len(name) < MIN_ALTERNATE_TITLE_LEN or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(name)
    return out


def main() -> int:
    if not CROSSWALK_PATH.exists():
        print(f"Crosswalk not found: {CROSSWALK_PATH}")
        return 1

    rows = load_crosswalk(CROSSWALK_PATH)
    print(f"Loaded {len(rows)} entities from {CROSSWALK_PATH.name}")

    # Merge by canonical original_name so aliases (e.g. CAS → Headquarters) share one record.
    by_key: dict[tuple[str, str], dict] = {}

    for i, row in enumerate(rows, 1):
        category = row["category"].strip()
        original_name = canonicalize_entity_name(row["original_name"].strip())
        openalex_id = row["openalex_id"].strip()
        openalex_name = (row.get("openalex_name") or "").strip()

        print(f"[{i}/{len(rows)}] {category}: {original_name}")
        entity = fetch_entity(category, openalex_id)
        time.sleep(RATE_LIMIT_DELAY)

        if entity is None:
            alts = []
            display_name = openalex_name
        else:
            alts = alternate_names(category, entity)
            display_name = entity.get("display_name") or openalex_name
            print(f"  display_name={display_name!r}, alternate_titles={len(alts)}")

        key = (category.lower(), original_name.lower())
        if key not in by_key:
            by_key[key] = {
                "category": category,
                "original_name": original_name,
                "openalex_id": openalex_id,
                "openalex_name": display_name,
                "alternate_titles": [],
                "_seen": set(),
            }
        rec = by_key[key]
        if display_name and not rec["openalex_name"]:
            rec["openalex_name"] = display_name
        for alt in alts:
            low = alt.lower()
            if low not in rec["_seen"]:
                rec["_seen"].add(low)
                rec["alternate_titles"].append(alt)

    records = []
    flat_rows = []
    for rec in by_key.values():
        alts = rec.pop("alternate_titles")
        rec.pop("_seen", None)
        records.append({**rec, "alternate_titles": alts})
        if alts:
            for alt in alts:
                flat_rows.append({**rec, "alternate_title": alt})
        else:
            flat_rows.append({**rec, "alternate_title": ""})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "original_name",
                "openalex_id",
                "openalex_name",
                "alternate_title",
            ],
        )
        writer.writeheader()
        writer.writerows(flat_rows)

    n_alts = sum(1 for r in flat_rows if r["alternate_title"])
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV} ({len(flat_rows)} rows, {n_alts} non-empty alternate titles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
