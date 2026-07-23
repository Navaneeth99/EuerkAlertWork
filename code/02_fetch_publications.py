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
# (connect timeout, read timeout) — avoids indefinite hang after laptop lock / dead sockets
REQUEST_TIMEOUT = (10, 60)

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


def _safe_err(exc: BaseException) -> str:
    """Strip API key from exception text before printing."""
    text = str(exc)
    if API_KEY:
        text = text.replace(API_KEY, "***")
    return text


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _save_checkpoint(checkpoint_path: Path, works: list, next_cursor: str | None, page: int) -> None:
    """Full-works resume checkpoint (large; only for non-dois-only mode)."""
    _atomic_write_json(
        checkpoint_path,
        {"works": works, "next_cursor": next_cursor, "page": page},
    )


def _save_slim_partial(
    path: Path,
    *,
    filter_str: str,
    next_cursor: str | None,
    page: int,
    n_fetched: int,
    total_count: int | None,
    dois: list,
) -> None:
    """Slim DOI resume checkpoint for --dois-only (safe for large orgs like CAS)."""
    _atomic_write_json(
        path,
        {
            "filter": filter_str,
            "next_cursor": next_cursor,
            "page": page,
            "n_fetched": n_fetched,
            "total_count": total_count,
            "dois": dois,
        },
    )


def _load_slim_partial(path: Path, expected_filter: str) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  Warning: could not read partial checkpoint ({_safe_err(e)}); starting fresh")
        return None
    if data.get("filter") != expected_filter:
        print("  Partial checkpoint filter mismatch; starting fresh")
        return None
    if not data.get("next_cursor"):
        print("  Partial checkpoint has no next_cursor; starting fresh")
        return None
    return data


def _load_full_checkpoint(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  Warning: could not read checkpoint ({_safe_err(e)}); starting fresh")
        return None
    if not data.get("next_cursor"):
        return None
    return data


def extract_short_id(openalex_id: str) -> str:
    """Extract the short ID from full OpenAlex URL."""
    # https://openalex.org/I19820366 -> I19820366
    return openalex_id.split("/")[-1] if openalex_id else ""


def extract_last_author(work: dict) -> tuple[str, str]:
    """Return (openalex_author_id, display_name) for the last author.

    Prefers author_position == \"last\"; falls back to the last authorship in the list
    (covers single-author works marked only as \"first\").
    """
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
    author_id = extract_short_id(author.get("id") or "")
    name = (author.get("display_name") or chosen.get("raw_author_name") or "").strip()
    return author_id, name


def extract_field(work: dict) -> tuple[str, str]:
    """Return (openalex_field_id, display_name) from primary_topic.field."""
    topic = work.get("primary_topic") or {}
    field = topic.get("field") or {}
    field_id = extract_short_id(field.get("id") or "")
    field_name = (field.get("display_name") or "").strip()
    return field_id, field_name


def work_to_doi_row(work: dict) -> dict | None:
    """Slim DOI sidecar row, including last-author and field when present."""
    doi = work.get("doi")
    if not doi:
        return None
    last_author_id, last_author_name = extract_last_author(work)
    field_id, field_name = extract_field(work)
    return {
        "doi": doi,
        "publication_date": work.get("publication_date"),
        "title": (work.get("display_name") or work.get("title") or "")[:100],
        "cited_by_count": work.get("cited_by_count", 0),
        "last_author_id": last_author_id,
        "last_author_name": last_author_name,
        "field_id": field_id,
        "field_name": field_name,
    }


def fetch_works_cursor(
    filter_str: str,
    entity_name: str,
    checkpoint_path: Path | None = None,
    select: str | None = None,
    *,
    slim_to_dois: bool = False,
) -> tuple[list, int]:
    """
    Fetch all works matching the filter using cursor pagination.

    Returns (records, n_fetched) where n_fetched is the number of API work objects
    seen. If slim_to_dois=True, records are DOI sidecar rows (authorships discarded
    after each page) — use this for --dois-only so large orgs do not OOM.

    When checkpoint_path is set:
      - slim_to_dois: writes/loads a slim partial (DOI rows + cursor)
      - else: writes/loads full works checkpoint
    Incomplete runs keep the checkpoint so the next invocation can resume.
    """
    all_records: list = []
    n_fetched = 0
    cursor, page = "*", 1
    total_count = None
    completed = False
    resume_cursor = cursor

    if checkpoint_path is not None:
        if slim_to_dois:
            partial = _load_slim_partial(checkpoint_path, filter_str)
            if partial:
                all_records = list(partial.get("dois") or [])
                n_fetched = int(partial.get("n_fetched") or 0)
                cursor = partial["next_cursor"]
                resume_cursor = cursor
                page = int(partial.get("page") or 1)
                total_count = partial.get("total_count")
                print(
                    f"  Resuming from partial: page {page}, "
                    f"{n_fetched:,} works fetched, {len(all_records):,} DOIs so far"
                )
        else:
            ckpt = _load_full_checkpoint(checkpoint_path)
            if ckpt:
                all_records = list(ckpt.get("works") or [])
                n_fetched = len(all_records)
                cursor = ckpt["next_cursor"]
                resume_cursor = cursor
                page = int(ckpt.get("page") or 1)
                print(f"  Resuming from checkpoint: page {page}, {n_fetched:,} works")

    try:
        while cursor:
            # Cursor for the page we are about to request (resume point if this fails).
            resume_cursor = cursor
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
                    response = requests.get(
                        f"{BASE_URL}/works",
                        params=params,
                        timeout=REQUEST_TIMEOUT,
                    )

                    if response.status_code in (400, 422):
                        print(f"\n  API error {response.status_code}: {response.text[:300]}")
                        cursor = None
                        break

                    if response.status_code == 429:
                        suggested = int(response.headers.get("Retry-After", 0))
                        backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                        wait = min(max(suggested, backoff), 120)  # cap at 2 minutes
                        print(
                            f"\n  Rate limited (429). Waiting {wait}s before "
                            f"retry {attempt + 1}/{MAX_RETRIES}..."
                        )
                        time.sleep(wait)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    works = data.get("results", [])
                    n_fetched += len(works)
                    if slim_to_dois:
                        for work in works:
                            row = work_to_doi_row(work)
                            if row:
                                all_records.append(row)
                    else:
                        all_records.extend(works)

                    meta = data.get("meta", {})
                    total_count = meta.get("count", 0)
                    cursor = meta.get("next_cursor")
                    # After a successful page, resume from the *next* cursor (not this page again).
                    if cursor:
                        resume_cursor = cursor

                    print_progress_bar(
                        n_fetched, total_count or n_fetched, prefix=f"Page {page:4d}"
                    )
                    page += 1

                    if checkpoint_path is not None and page % CHECKPOINT_EVERY == 0 and cursor:
                        if slim_to_dois:
                            _save_slim_partial(
                                checkpoint_path,
                                filter_str=filter_str,
                                next_cursor=cursor,
                                page=page,
                                n_fetched=n_fetched,
                                total_count=total_count,
                                dois=all_records,
                            )
                        else:
                            _save_checkpoint(checkpoint_path, all_records, cursor, page)

                    if not cursor:
                        completed = True

                    time.sleep(RATE_LIMIT_DELAY)
                    break  # success — exit retry loop

                except requests.RequestException as e:
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    if attempt < MAX_RETRIES - 1:
                        print(
                            f"\n  Error on page {page} (attempt {attempt + 1}/{MAX_RETRIES}): "
                            f"{_safe_err(e)}. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        print(
                            f"\n  Error fetching page {page} after {MAX_RETRIES} attempts: "
                            f"{_safe_err(e)}"
                        )
                        cursor = None  # stop pagination; keep partial for resume
            else:
                # All retries exhausted via 429 loop
                print(f"\n  Giving up on page {page} after {MAX_RETRIES} rate-limit retries.")
                cursor = None
    except KeyboardInterrupt:
        print("\n  Interrupted — saving partial progress before exit...")
        cursor = None

    # Print newline after progress bar completes
    print()

    if checkpoint_path is not None:
        if completed:
            if checkpoint_path.exists():
                checkpoint_path.unlink()
        elif n_fetched or all_records:
            # Persist so the next run can resume (including pages since last periodic save).
            if slim_to_dois:
                _save_slim_partial(
                    checkpoint_path,
                    filter_str=filter_str,
                    next_cursor=resume_cursor,
                    page=page,
                    n_fetched=n_fetched,
                    total_count=total_count,
                    dois=all_records,
                )
                print(
                    f"  Saved partial progress ({n_fetched:,} works, {len(all_records):,} DOIs) "
                    f"→ {checkpoint_path.name}"
                )
            else:
                _save_checkpoint(checkpoint_path, all_records, resume_cursor, page)
                print(f"  Saved checkpoint ({n_fetched:,} works) → {checkpoint_path.name}")

    return all_records, n_fetched


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


def process_entity(
    category: str,
    original_name: str,
    openalex_id: str,
    openalex_name: str,
    dois_only: bool = False,
    force: bool = False,
):
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

    # Full-works mode: large checkpoint. DOIs-only: slim partial (rows + cursor).
    if dois_only:
        checkpoint_path = category_dir / f"{safe_name}_dois.partial.json"
    else:
        checkpoint_path = category_dir / f"{safe_name}.checkpoint.json"

    if force and checkpoint_path.exists():
        checkpoint_path.unlink()
        print(f"  Cleared stale progress file (--force): {checkpoint_path.name}")

    print(f"\nFetching: {original_name}")
    print(f"  Filter: {filter_str}")

    if dois_only:
        # Include authorships for last_author_*; slim each page immediately so
        # we never hold ~600k full work objects in memory.
        doi_select = (
            "id,doi,display_name,publication_date,cited_by_count,authorships,primary_topic"
        )
        doi_list, n_fetched = fetch_works_cursor(
            filter_str,
            original_name,
            checkpoint_path=checkpoint_path,
            select=doi_select,
            slim_to_dois=True,
        )
        if n_fetched == 0:
            print("  No works found")
            return None
        # Incomplete fetch (errors exhausted): keep partial, do not write final sidecar.
        if checkpoint_path.exists():
            print(
                f"  Incomplete — resume later with the same command "
                f"(progress in {checkpoint_path.name})"
            )
            return None
        doi_path = category_dir / f"{safe_name}_dois.json"
        with open(doi_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "entity": original_name,
                    "total_works": n_fetched,
                    "works_with_doi": len(doi_list),
                    "dois": doi_list,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"  Saved {len(doi_list):,} DOIs (+ last author, field) to: {doi_path.name}")
        return n_fetched

    works, n_fetched = fetch_works_cursor(
        filter_str, original_name, checkpoint_path=checkpoint_path, select=None
    )
    if checkpoint_path.exists():
        print(
            f"  Incomplete — resume later with the same command "
            f"(progress in {checkpoint_path.name})"
        )
        return None
    if not works:
        print("  No works found")
        return None

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

    # Build lightweight DOI sidecar (with last author from full works)
    doi_list = []
    for work in works:
        row = work_to_doi_row(work)
        if row:
            doi_list.append(row)

    doi_path = category_dir / f"{safe_name}_dois.json"
    with open(doi_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "entity": original_name,
                "total_works": len(works),
                "works_with_doi": len(doi_list),
                "dois": doi_list,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

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
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch from scratch even when output/partial files exist (overwrite)",
    )
    args = parser.parse_args()
    dois_only: bool = args.dois_only
    force: bool = args.force

    print("=" * 70)
    print("OpenAlex Publication Fetcher")
    print(f"Date range: {START_DATE} to present")
    print(f"Email: {EMAIL}")
    if dois_only:
        print("Mode: DOIs-only (skipping full works JSON)")
        print("Resume: incomplete entities continue from *_dois.partial.json")
    if force:
        print("Mode: FORCE re-fetch (existing outputs/partials will be overwritten)")
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
        if done_file.exists() and not force:
            print(f"  Output file exists, skipping (delete to re-fetch, or pass --force)")
            processed_ids.add(openalex_id)
            results[category]["skipped"] += 1
            continue
        if done_file.exists() and force:
            print(f"  Output file exists — re-fetching (--force)")

        works_count = process_entity(
            category,
            original_name,
            openalex_id,
            openalex_name,
            dois_only=dois_only,
            force=force,
        )
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
