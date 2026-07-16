"""
Fetch publications (DOIs) from OpenAlex for all entities in the crosswalk.
Publications from 2015 to present.
"""

import csv
import json
import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

PRJ_ROOT = Path(__file__).resolve().parents[1]
env_path = PRJ_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# OpenAlex API Key — loaded from .env (OPENALEX_API=<your key>)
API_KEY = os.environ.get("OPENALEX_API")
if not API_KEY:
    print("WARNING: OPENALEX_API not found in .env — running without API key (IP-based rate limit applies)")

# Configuration
EMAIL = "navaneethbiju@gmail.com"
BASE_URL = "https://api.openalex.org"
START_DATE = "2015-01-01"
PER_PAGE = 200  # Max allowed by OpenAlex
RATE_LIMIT_DELAY = 0.1  # Seconds between requests (polite pool with email = 10 req/sec)
MAX_RETRIES = 6
RETRY_BACKOFF_BASE = 2  # seconds; wait doubles each retry: 2, 4, 8, 16, 32, 64
CHECKPOINT_EVERY = 50  # save progress every N pages (~10K works)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CROSSWALK_PATH = PROJECT_DIR / "rawdata" / "Institution_OpenAlexCrossWalk" / "openalex_crosswalk_clean.csv"
OUTPUT_DIR = PROJECT_DIR / "rawdata" / "PublicationData"


def print_progress_bar(current: int, total: int, bar_length: int = 40, prefix: str = ""):
    """Print a progress bar to the console."""
    if total == 0:
        return

    percent = current / total
    filled_length = int(bar_length * percent)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    # Print on same line
    print(f"\r  {prefix} |{bar}| {current:,}/{total:,} ({percent*100:.1f}%)", end="", flush=True)


def _save_checkpoint(checkpoint_path: Path, works: list, next_cursor: str | None, page: int) -> None:
    tmp = checkpoint_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"works": works, "next_cursor": next_cursor, "page": page}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(checkpoint_path)


def fetch_works_cursor(filter_str: str, entity_name: str, checkpoint_path: Path | None = None,
                       select: str | None = None) -> list:
    """
    Fetch all works matching the filter using cursor pagination.
    If checkpoint_path is given, saves progress every CHECKPOINT_EVERY pages
    and resumes from an existing checkpoint on restart.
    If select is given, only those comma-separated fields are returned by the
    API (e.g. "id,doi,display_name,publication_date,cited_by_count"), keeping
    both transfer size and checkpoint size small.
    """
    all_works, cursor, page = [], "*", 1
    total_count = None

    while cursor:
        params = {
            "mailto": EMAIL,
            "filter": filter_str,
            "per_page": PER_PAGE,
            "cursor": cursor,
        }
        if API_KEY:
            params["api_key"] = API_KEY
        if select:
            params["select"] = select

        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(f"{BASE_URL}/works", params=params)

                if response.status_code in (400, 422):
                    print(f"\n  API error {response.status_code}: {response.text[:300]}")
                    cursor = None
                    break

                if response.status_code == 429:
                    suggested = int(response.headers.get("Retry-After", 0))
                    backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                    wait = min(max(suggested, backoff), 120)  # cap at 2 minutes
                    print(f"\n  Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                works = data.get("results", [])
                all_works.extend(works)

                meta = data.get("meta", {})
                total_count = meta.get("count", 0)
                cursor = meta.get("next_cursor")

                print_progress_bar(len(all_works), total_count, prefix=f"Page {page:4d}")
                page += 1

                if checkpoint_path is not None and page % CHECKPOINT_EVERY == 0:
                    _save_checkpoint(checkpoint_path, all_works, cursor, page)

                time.sleep(RATE_LIMIT_DELAY)
                break  # success — exit retry loop

            except requests.RequestException as e:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    print(f"\n  Error on page {page} (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"\n  Error fetching page {page} after {MAX_RETRIES} attempts: {e}")
                    cursor = None  # stop pagination
        else:
            # All retries exhausted via 429 loop
            print(f"\n  Giving up on page {page} after {MAX_RETRIES} rate-limit retries.")
            cursor = None

    # Print newline after progress bar completes
    print()

    if checkpoint_path is not None and checkpoint_path.exists():
        checkpoint_path.unlink()

    return all_works


def extract_short_id(openalex_id: str) -> str:
    """Extract the short ID from full OpenAlex URL."""
    # https://openalex.org/I19820366 -> I19820366
    return openalex_id.split("/")[-1] if openalex_id else ""


def sanitize_filename(name: str) -> str:
    """Create a safe filename from entity name."""
    # Replace problematic characters
    replacements = {
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "",
        ",": "",
        " ": "_",
    }
    result = name
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result[:100]  # Limit length


def process_entity(category: str, original_name: str, openalex_id: str, openalex_name: str, dois_only: bool = False):
    """
    Process a single entity: fetch works and save to file.
    If dois_only=True, only the lightweight _dois.json sidecar is written.
    """
    short_id = extract_short_id(openalex_id)

    # Build filter based on category
    if category == "journal":
        # For journals/sources, filter by source ID
        filter_str = f"primary_location.source.id:{short_id},from_publication_date:{START_DATE}"
    elif category == "institution":
        # For institutions, filter by institution ID in authorships
        filter_str = f"authorships.institutions.id:{short_id},from_publication_date:{START_DATE}"
    elif category == "publisher":
        # For publishers, filter by publisher lineage
        filter_str = f"primary_location.source.publisher_lineage:{short_id},from_publication_date:{START_DATE}"
    else:
        print(f"  Unknown category: {category}, skipping")
        return None


    safe_name = sanitize_filename(original_name)
    category_dir = OUTPUT_DIR / f"{category.capitalize()}s"
    category_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = category_dir / f"{safe_name}.checkpoint.json"

    # In dois_only mode keep only the 5 fields needed for the sidecar.
    # Full work objects (~5KB each) are fetched from the API but discarded
    # immediately after extracting these fields, so memory stays low.

    print(f"\nFetching: {original_name}")
    print(f"  Filter: {filter_str}")
    # In dois_only mode ask the API to return only the 5 fields needed for
    # the sidecar. This keeps each work object ~25x smaller, so both the
    # in-memory list and the checkpoint file stay small.
    doi_select = "id,doi,display_name,publication_date,cited_by_count" if dois_only else None
    works = fetch_works_cursor(filter_str, original_name, checkpoint_path=checkpoint_path,
                               select=doi_select)

    if not works:
        print(f"  No works found")
        return None

    if not dois_only:
        output_data = {
            "metadata": {
                "original_name": original_name,
                "openalex_id": openalex_id,
                "openalex_name": openalex_name,
                "category": category,
                "filter_used": filter_str,
                "fetch_date": datetime.now().isoformat(),
                "total_works": len(works),
                "date_range": f"{START_DATE} to present",
            },
            "works": works,
        }
        output_path = category_dir / f"{safe_name}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(works)} works to: {output_path.name}")

    # Build lightweight DOI sidecar
    # display_name is used when select is active; title is the fallback for full fetches
    doi_list = []
    for work in works:
        doi = work.get("doi")
        pub_date = work.get("publication_date")
        title = (work.get("display_name") or work.get("title") or "")[:100]
        if doi:
            doi_list.append({
                "doi": doi,
                "publication_date": pub_date,
                "title": title,
                "cited_by_count": work.get("cited_by_count", 0),
            })

    doi_path = category_dir / f"{safe_name}_dois.json"
    with open(doi_path, "w", encoding="utf-8") as f:
        json.dump({
            "entity": original_name,
            "total_works": len(works),
            "works_with_doi": len(doi_list),
            "dois": doi_list,
        }, f, indent=2, ensure_ascii=False)

    return len(works)


def load_crosswalk() -> list:
    """Load the crosswalk CSV file."""
    entities = []
    with open(CROSSWALK_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities.append(row)
    return entities


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch publications from OpenAlex")
    parser.add_argument(
        "--dois-only", action="store_true",
        help="Save only the lightweight _dois.json sidecar; skip the full works JSON"
    )
    args = parser.parse_args()
    dois_only: bool = args.dois_only

    print("=" * 70)
    print("OpenAlex Publication Fetcher")
    print(f"Date range: {START_DATE} to present")
    print(f"Email: {EMAIL}")
    if dois_only:
        print("Mode: DOIs-only (skipping full works JSON)")
    print("=" * 70)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load crosswalk
    entities = load_crosswalk()
    print(f"\nLoaded {len(entities)} entities from crosswalk")

    # Track processed OpenAlex IDs to skip duplicates
    processed_ids = set()

    # Track progress
    results = {
        "journal": {"processed": 0, "total_works": 0, "skipped": 0},
        "institution": {"processed": 0, "total_works": 0, "skipped": 0},
        "publisher": {"processed": 0, "total_works": 0, "skipped": 0},
    }

    # Process each entity
    for i, entity in enumerate(entities):
        category = entity["category"]
        original_name = entity["original_name"]
        openalex_id = entity["openalex_id"]
        openalex_name = entity["openalex_name"]

        print(f"\n[{i+1}/{len(entities)}] Processing {category}: {original_name}")

        if not openalex_id:
            print("  No OpenAlex ID, skipping")
            continue

        # Skip duplicate OpenAlex IDs (e.g., CAS Headquarters = CAS)
        if openalex_id in processed_ids:
            print(f"  Duplicate OpenAlex ID (already processed), skipping")
            results[category]["skipped"] += 1
            continue

        # Check if output file already exists (resume capability)
        safe_name = sanitize_filename(original_name)
        category_dir = OUTPUT_DIR / f"{category.capitalize()}s"
        done_file = category_dir / (f"{safe_name}_dois.json" if dois_only else f"{safe_name}.json")
        if done_file.exists():
            print(f"  Output file exists, skipping (delete to re-fetch)")
            processed_ids.add(openalex_id)
            results[category]["skipped"] += 1
            continue

        works_count = process_entity(category, original_name, openalex_id, openalex_name, dois_only=dois_only)
        processed_ids.add(openalex_id)

        if works_count:
            results[category]["processed"] += 1
            results[category]["total_works"] += works_count

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for category, stats in results.items():
        print(f"{category.capitalize()}s: {stats['processed']} processed, {stats['skipped']} skipped, {stats['total_works']:,} total works")

    print(f"\nOutput saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
