"""Map EurekAlert org/journal names to doi_list entities via weighted word similarity.

Usage: python code/build_pr_entity_crosswalk.py [--min-score 90]
"""

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent
DOI_CSV = ROOT / "Processed" / "DOIList.csv"
PR_GLOB = (ROOT / "Processed/EurekAlert/Press_release/*.parquet").as_posix()
XW = ROOT / "rawdata/Institution_OpenAlexCrossWalk/openalex_crosswalk_clean.csv"
OUT = ROOT / "Processed/pr_entity_crosswalk.json"
OUT_CSV = ROOT / "Processed/pr_entity_crosswalk_review.csv"

SKIP = {"of", "the", "and", "for", "in", "on", "a", "an", "at", "to", "by", "de", "la", "le", "as"}

ORG_ALIASES = {
    "The University of Tokyo": "University of Tokyo",
    "Kyoto University": "University of Kyoto",
    "Chinese Academy of Science": "Chinese Academy of Sciences",
    "Chinese Academy of Sciences": "Chinese Academy of Sciences",
    "University of Science and Technology of China": "University of Science and Technology of China",
    "Institute of Physics, Chinese Academy of Sciences": "Institute of Physics, Chinese Academy of Sciences",
    "Shenzhen Institutes of Advanced Technology": "Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences",
    "Shenzhen Institute of Advanced Technology": "Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences",
    "Dalian Institute of Chemical Physics": "Dalian Institute of Chemical Physics, Chinese Academy Sciences",
    "Changchun Institute of Optics, Fine Mechanics and Physics": "Light Publishing Center, Changchun Institute of Optics, Fine Mechanics And Physics, CAS",
    "Institute of Geographic Sciences and Natural Resources Research": "IGSNRR CAS",
    "Aerospace Information Research Institute": "Aerospace Information Research Institute, Chinese Academy of Sciences",
    "Institute of Atmospheric Physics": "Institute of Atmospheric Physics, Chinese Academy of Sciences",
    "Institute of Process Engineering": "Institute of Process Engineering, Chinese Academy of Sciences",
    "Hefei Institutes of Physical Science": "Hefei Institutes of Physical Science, Chinese Academy of Sciences",
    "Beijing Institute of Technology": "Beijing Institute of Technology Press Co., Ltd",
    "BME Frontiers": "BMEF (BME Frontiers)",
    "Space Science & Technology": "Space: Science & Technology",
    "Ocean-Land-Atmosphere Research": "Ocean-Land-Atmosphere Research (OLAR)",
}

GENERIC_ORG = {
    "university", "institute", "institutes", "institution", "academy", "sciences", "science",
    "school", "college", "department", "faculty", "center", "centre", "national",
    "international", "graduate", "press", "research", "laboratory", "lab", "labs",
    "hospital", "medical", "medicine", "technology", "technological", "advanced",
    "studies", "society", "association", "federation", "group", "headquarters",
    "publishing", "publisher", "limited", "ltd", "inc", "corp", "foundation",
    "organization", "organisation", "division", "office", "council", "committee",
    "health", "public", "applied", "physical", "physics", "chemical", "chemistry",
    "engineering", "biological", "biomedical", "life", "earth", "environmental",
    "graduate", "undergraduate", "state", "federal", "royal", "general",
}

GENERIC_JOURNAL = GENERIC_ORG | {
    "journal", "review", "letters", "communications", "reports", "nature", "cell",
    "open", "frontiers", "systems", "materials", "energy", "space", "data", "annals",
    "proceedings", "bulletin", "international", "american", "european", "british",
    "clinical", "experimental", "theoretical", "applied", "annual", "quarterly",
}


def _word_ratio(a, b):
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b)
    except ImportError:
        return int(SequenceMatcher(None, a, b).ratio() * 100)


def progress_bar(current, total, prefix="", width=40):
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  {prefix} |{bar}| {current:,}/{total:,} ({pct * 100:.1f}%)", end="", flush=True)
    if current == total:
        print()


def norm(s):
    s = re.sub(r"[^\w\s&:/-]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def tokenize(s):
    return [t for t in norm(s).split() if t and t not in SKIP]


def is_generic(tok, field="org"):
    g = GENERIC_JOURNAL if field == "journal" else GENERIC_ORG
    return tok in g or len(tok) <= 2


def acronym(name):
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    letters = [w[0].upper() for w in words if w.lower() not in SKIP and len(w) > 1]
    short = "".join(letters)
    return short if len(short) >= 3 else ""


def load_entities():
    rows = duckdb.execute(f"""
        SELECT DISTINCT entity_name, category
        FROM read_csv('{DOI_CSV.as_posix()}', header=true, auto_detect=true)
        ORDER BY entity_name
    """).fetchall()
    oa = {}
    with XW.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            oa[r["original_name"]] = (r.get("openalex_name") or "").strip()
    return [{"entity_name": n, "category": c, "openalex_name": oa.get(n, "")} for n, c in rows]


def labels(ent):
    out = [(ent["entity_name"], ent["category"], ent["entity_name"], "entity_name")]
    if ent["openalex_name"]:
        out.append((ent["entity_name"], ent["category"], ent["openalex_name"], "openalex_name"))
    acr = acronym(ent["entity_name"])
    if acr:
        out.append((ent["entity_name"], ent["category"], acr, "acronym"))
    for alias, target in ORG_ALIASES.items():
        if target == ent["entity_name"]:
            out.append((ent["entity_name"], ent["category"], alias, "manual_alias"))
    return out


def weighted_word_score(left, label, field="org"):
    if norm(left) == norm(label):
        return 100, "exact"

    dist_l = [t for t in tokenize(left) if not is_generic(t, field)]
    dist_r = [t for t in tokenize(label) if not is_generic(t, field)]

    if not dist_l:
        return (100, "exact") if norm(left) == norm(label) else (0, "generic_only")
    if not dist_r:
        return 0, "no_distinctive_target"

    used = set()
    matches = 0
    for lw in dist_l:
        for i, rw in enumerate(dist_r):
            if i in used:
                continue
            if lw == rw or _word_ratio(lw, rw) >= 88:
                used.add(i)
                matches += 1
                break

    if matches == 0:
        return 0, "no_word_match"

    recall = matches / len(dist_l)
    if recall < 1.0:
        return int(100 * recall), "partial_words"

    if len(dist_l) == 1 and len(dist_r) > 1:
        return 85, "ambiguous_token"

    if len(dist_l) == len(dist_r) == 1:
        raw_l, raw_r = tokenize(left), tokenize(label)
        if len(raw_l) > 2 or len(raw_r) > 2:
            return 85, "single_token_short_name"

    if len(dist_r) > len(dist_l):
        return int(100 * len(dist_l) / len(dist_r)), "extra_entity_words"

    return 100, "word_match"


def score(left, label, label_type, field="org"):
    if not norm(left) or not norm(label):
        return 0, "empty"
    if label_type in ("entity_name", "openalex_name", "manual_alias") and norm(left) == norm(label):
        return 100, "exact"
    if label_type == "acronym":
        return (100, "acronym_exact") if norm(left).replace(" ", "") == norm(label).replace(" ", "") else (0, "acronym_miss")
    return weighted_word_score(left, label, field)


def best_match(name, pool, cats=None, field="org"):
    best = None
    for entity_name, category, label, label_type in pool:
        if cats and category not in cats:
            continue
        sc, kind = score(name, label, label_type, field)
        if not best or sc > best["score"]:
            best = {
                "entity_name": entity_name,
                "category": category,
                "score": sc,
                "matched_label": label,
                "label_type": label_type,
                "match_kind": kind,
            }
    return best


def load_pr_names():
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW pr AS SELECT * FROM read_parquet('{PR_GLOB}', union_by_name=true)")
    orgs = con.execute("""
        SELECT trim("Organization") AS name, count(*)::INT AS n
        FROM pr WHERE trim("Organization") != ''
        GROUP BY 1 ORDER BY n DESC
    """).fetchall()
    journals = con.execute("""
        SELECT name, list(source) AS sources, sum(n)::INT AS n FROM (
            SELECT trim("Journal (Matched)") AS name, 'journal_matched' AS source, count(*) AS n
            FROM pr WHERE trim("Journal (Matched)") != '' GROUP BY 1
            UNION ALL
            SELECT trim("Journal (Typed)"), 'journal_typed', count(*)
            FROM pr WHERE trim("Journal (Typed)") != '' GROUP BY 1
        ) GROUP BY 1 ORDER BY n DESC
    """).fetchall()
    jmap = {name: {"sources": sources, "n": n} for name, sources, n in journals}
    return orgs, jmap


def build(min_score):
    print("Loading doi_list entities...")
    entities = load_entities()
    pool = [x for e in entities for x in labels(e)]
    org_pool = [x for x in pool if x[1] in ("institution", "publisher")]
    j_pool = [x for x in pool if x[1] == "journal"]

    print("Loading press release names...")
    orgs, journals = load_pr_names()
    print(f"  {len(entities)} entities, {len(orgs):,} organizations, {len(journals):,} journals")

    org_map, org_details = {}, {}
    print("Matching organizations (word-weighted)...")
    for i, (name, n) in enumerate(orgs, 1):
        hit = best_match(name, org_pool, field="org")
        if hit:
            hit["pr_count"] = n
            hit["accepted"] = hit["score"] >= min_score
            org_details[name] = hit
            if hit["accepted"]:
                org_map[name] = hit["entity_name"]
        if i == 1 or i % 25 == 0 or i == len(orgs):
            progress_bar(i, len(orgs), "organizations")

    j_map, j_details = {}, {}
    j_min = max(min_score, 92)
    print("Matching journals (word-weighted)...")
    for i, (name, meta) in enumerate(journals.items(), 1):
        hit = best_match(name, j_pool, field="journal")
        if hit:
            hit["pr_count"] = meta["n"]
            hit["sources"] = meta["sources"]
            hit["accepted"] = hit["score"] >= j_min
            j_details[name] = hit
            if hit["accepted"]:
                j_map[name] = hit["entity_name"]
        if i == 1 or i % 100 == 0 or i == len(journals):
            progress_bar(i, len(journals), "journals")

    payload = {
        "organizations": org_map,
        "journals": j_map,
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "min_score_org": min_score,
            "min_score_journal": j_min,
            "scoring": "weighted_word_match",
            "doi_entities": len(entities),
            "pr_organizations": len(orgs),
            "pr_journals": len(journals),
            "mapped_organizations": len(org_map),
            "mapped_journals": len(j_map),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print("Writing output files...")
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pr_field", "pr_name", "entity_name", "entity_category", "score", "accepted", "matched_label", "label_type", "match_kind", "pr_count"])
        for name, d in org_details.items():
            w.writerow(["organization", name, d["entity_name"], d["category"], d["score"], d["accepted"], d["matched_label"], d["label_type"], d.get("match_kind", ""), d["pr_count"]])
        for name, d in j_details.items():
            w.writerow(["journal", name, d["entity_name"], d["category"], d["score"], d["accepted"], d["matched_label"], d["label_type"], d.get("match_kind", ""), d["pr_count"]])

    print(f"Wrote {OUT} ({len(org_map)} orgs, {len(j_map)} journals accepted)")
    print(f"Wrote {OUT_CSV}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-score", type=int, default=90)
    args = p.parse_args()
    build(args.min_score)

if __name__ == "__main__":
    main()
