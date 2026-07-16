"""Extract DOIs from PublicationData into Processed/DOIList.csv.

Uses lightweight *_dois.json sidecars (~MB) instead of full work JSON (~GB).
Streams rows to CSV so memory stays bounded. Run from a terminal, not the IDE:

  python code/03_extract_dois.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUB = ROOT / "rawdata" / "PublicationData"
XW = ROOT / "rawdata" / "Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv"
OUT = ROOT / "Processed" / "DOIList.csv"


def load_entity_lookup():
    lookup = {}
    with XW.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            info = (row["original_name"], row["openalex_id"], row["category"])
            lookup[row["original_name"]] = info
            if row["openalex_name"]:
                lookup[row["openalex_name"]] = info
    return lookup


def clean_doi(doi):
    return doi[16:] if doi.startswith("https://doi.org/") else doi


def iter_dois_file(path, lookup):
    data = json.loads(path.read_text(encoding="utf-8"))
    entity = data.get("entity", "")
    ent, oa_id, cat = lookup.get(entity, (entity, "", ""))

    if "dois" in data:
        for item in data["dois"]:
            doi = item.get("doi")
            if not doi:
                continue
            title = (item.get("title") or item.get("display_name") or "").strip()
            cited = item.get("cited_by_count") or 0
            yield ent, oa_id, cat, clean_doi(doi), item.get("publication_date", ""), title, cited
        return

    meta = data.get("metadata", {})
    ent = meta.get("original_name", entity)
    oa_id = meta.get("openalex_id", lookup.get(ent, ("", "", ""))[1])
    cat = meta.get("category", lookup.get(ent, ("", "", ""))[2])
    for work in data.get("works", []):
        doi = work.get("doi")
        if not doi:
            continue
        title = (work.get("title") or work.get("display_name") or "").strip()
        cited = work.get("cited_by_count") or 0
        yield ent, oa_id, cat, clean_doi(doi), work.get("publication_date", ""), title, cited


def data_files():
    files = []
    for cat in ("Journals", "Institutions", "Publishers"):
        d = PUB / cat
        if not d.exists():
            continue
        dois = sorted(d.glob("*_dois.json"))
        if dois:
            files.extend(dois)
        else:
            files.extend(f for f in d.glob("*.json") if not f.name.endswith("_dois.json"))
    # full JSON fallback only when no sidecar exists (Ecosystem Health)
    have = {f.name.replace("_dois.json", ".json") for f in files if f.name.endswith("_dois.json")}
    for cat in ("Journals", "Institutions", "Publishers"):
        d = PUB / cat
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.name.endswith("_dois.json") or f.name in have:
                continue
            files.append(f)
    return sorted(files, key=lambda p: p.stat().st_size)


def main():
    lookup = load_entity_lookup()
    files = data_files()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    print(f"Processing {len(files)} files (smallest first)...")
    total = 0
    by_cat = Counter()

    with OUT.open("w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["entity_name", "openalex_id", "category", "doi", "publication_date", "title", "cited_by_count"])
        for i, path in enumerate(files, 1):
            mb = path.stat().st_size / (1024 * 1024)
            print(f"[{i}/{len(files)}] {path.name[:55]:<55} {mb:7.1f} MB", flush=True)
            n = 0
            for row in iter_dois_file(path, lookup):
                w.writerow(row)
                n += 1
                by_cat[row[2]] += 1
            total += n
            print(f"  -> {n:,} rows (running total {total:,})", flush=True)

    print(f"\nWrote {total:,} rows to {OUT} ({OUT.stat().st_size / 1024 / 1024:.1f} MB)")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat or '(unknown)'}: {n:,}")


if __name__ == "__main__":
    main()
