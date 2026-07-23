"""Extract DOIs from PublicationData into Processed/DOIList.csv.

Uses lightweight *_dois.json sidecars (~MB) instead of full work JSON (~GB).
Streams rows to CSV so memory stays bounded. Includes last-author and OpenAlex
field (primary_topic.field) for fixed-effects specs. Run from a terminal:

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

DOI_HEADER = [
    "entity_name",
    "openalex_id",
    "category",
    "doi",
    "publication_date",
    "title",
    "cited_by_count",
    "last_author_id",
    "last_author_name",
    "field_id",
    "field_name",
]


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


def extract_last_author(work: dict) -> tuple[str, str]:
    """Mirror 02_fetch_publications.extract_last_author for full-work JSON fallback."""
    authorships = work.get("authorships") or []
    chosen = None
    for authorship in authorships:
        if authorship.get("author_position") == "last":
            chosen = authorship
            break
    if chosen is None and authorships:
        chosen = authorships[-1]
    if not chosen:
        return "", ""
    author = chosen.get("author") or {}
    author_id = (author.get("id") or "").rsplit("/", 1)[-1]
    name = (author.get("display_name") or chosen.get("raw_author_name") or "").strip()
    return author_id, name


def extract_field(work: dict) -> tuple[str, str]:
    """Mirror 02_fetch_publications.extract_field for full-work JSON fallback."""
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    field_id = (field.get("id") or "").rsplit("/", 1)[-1]
    field_name = (field.get("display_name") or "").strip()
    return field_id, field_name


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
            last_id = (item.get("last_author_id") or "").strip()
            last_name = (item.get("last_author_name") or "").strip()
            field_id = (item.get("field_id") or "").strip()
            field_name = (item.get("field_name") or "").strip()
            yield (
                ent,
                oa_id,
                cat,
                clean_doi(doi),
                item.get("publication_date", ""),
                title,
                cited,
                last_id,
                last_name,
                field_id,
                field_name,
            )
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
        last_id, last_name = extract_last_author(work)
        field_id, field_name = extract_field(work)
        yield (
            ent,
            oa_id,
            cat,
            clean_doi(doi),
            work.get("publication_date", ""),
            title,
            cited,
            last_id,
            last_name,
            field_id,
            field_name,
        )


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
    with_last = 0
    with_field = 0
    by_cat = Counter()

    with OUT.open("w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(DOI_HEADER)
        for i, path in enumerate(files, 1):
            mb = path.stat().st_size / (1024 * 1024)
            print(f"[{i}/{len(files)}] {path.name[:55]:<55} {mb:7.1f} MB", flush=True)
            n = 0
            for row in iter_dois_file(path, lookup):
                w.writerow(row)
                n += 1
                by_cat[row[2]] += 1
                if row[7]:
                    with_last += 1
                if row[9]:
                    with_field += 1
            total += n
            print(f"  -> {n:,} rows (running total {total:,})", flush=True)

    print(f"\nWrote {total:,} rows to {OUT} ({OUT.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  with last_author_id: {with_last:,} ({100 * with_last / total:.1f}%)" if total else "")
    print(f"  with field_id: {with_field:,} ({100 * with_field / total:.1f}%)" if total else "")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat or '(unknown)'}: {n:,}")


if __name__ == "__main__":
    main()
