"""
OpenAlex Crosswalk Script
Creates a mapping between our institution/journal list and OpenAlex IDs
"""

import requests
import json
import csv
import time
from pathlib import Path

BASE_URL = "https://api.openalex.org"

# Add polite pool email for better rate limits (optional but recommended)
PARAMS = {"mailto": "research@example.com"}

# Our entities categorized by OpenAlex entity type
JOURNALS = [
    "Advanced Devices & Instrumentation",
    "Energy Material Advances",
    "Space: Science & Technology",
    "Cyborg and Bionic Systems",
    "BioDesign Research",
    "Biomaterials Research",
    "BMEF",
    "BME Frontiers",
    "Ecosystem Health and Sustainability",
    "Health Data Science",
    "Intelligent Computing",
    "Journal of Bio-X Research",
    "Journal of Remote Sensing",
    "Ocean-Land-Atmosphere Research",
    "OLAR",
    "Plant Phenomics",
    "Research",
    "Ultrafast Science",
    "Journal of EMDR Practice and Research",
]

INSTITUTIONS = [
    "Chinese Academy of Sciences",
    "University of Science and Technology of China",
    "Institute of Physics of the Czech Academy of Sciences",
    "Institute of Process Engineering, Chinese Academy of Sciences",
    "Institute of Atmospheric Physics, Chinese Academy of Sciences",
    "Aerospace Information Research Institute, Chinese Academy of Sciences",
    "Dalian Institute of Chemical Physics, Chinese Academy of Sciences",
    "Changchun Institute of Optics, Fine Mechanics and Physics",
    "Hefei Institutes of Physical Science, Chinese Academy of Sciences",
    "Shenzhen Institute of Advanced Technology, Chinese Academy of Sciences",
    "Institute of Geographic Sciences and Natural Resources Research",  # IGSNRR CAS
    "Nagoya University",
    "Hokkaido University",
    "University of Tokyo",
    "Kyoto University",
    "Osaka Metropolitan University",
    "Osaka City University",
    "Osaka Prefecture University",
]

PUBLISHERS = [
    "Beijing Institute of Technology Press",
    "Higher Education Press",
    "Tsinghua University Press",
    "Shanghai Jiao Tong University",
]


def search_openalex(entity_type: str, query: str) -> list:
    """
    Search OpenAlex for an entity by name.

    Args:
        entity_type: One of 'institutions', 'sources', 'publishers'
        query: Search term

    Returns:
        List of matching results
    """
    url = f"{BASE_URL}/{entity_type}"
    params = {
        **PARAMS,
        "search": query,
        "per_page": 5,  # Get top 5 matches
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.RequestException as e:
        print(f"Error searching for '{query}': {e}")
        return []


def extract_institution_info(result: dict) -> dict:
    """Extract relevant info from an institution result."""
    return {
        "openalex_id": result.get("id", ""),
        "display_name": result.get("display_name", ""),
        "ror": result.get("ror", ""),
        "country_code": result.get("country_code", ""),
        "type": result.get("type", ""),
        "works_count": result.get("works_count", 0),
        "alternate_names": result.get("display_name_alternatives", []),
    }


def extract_source_info(result: dict) -> dict:
    """Extract relevant info from a source (journal) result."""
    return {
        "openalex_id": result.get("id", ""),
        "display_name": result.get("display_name", ""),
        "issn_l": result.get("issn_l", ""),
        "issn": result.get("issn", []),
        "type": result.get("type", ""),
        "works_count": result.get("works_count", 0),
        "host_organization": result.get("host_organization_name", ""),
        "alternate_names": result.get("alternate_titles", []),
    }


def extract_publisher_info(result: dict) -> dict:
    """Extract relevant info from a publisher result."""
    return {
        "openalex_id": result.get("id", ""),
        "display_name": result.get("display_name", ""),
        "sources_count": result.get("sources_count", 0),
        "works_count": result.get("works_count", 0),
        "alternate_names": result.get("alternate_titles", []),

    }


def create_crosswalk():
    """Main function to create the crosswalk."""
    results = {
        "journals": [],
        "institutions": [],
        "publishers": [],
    }

    print("=" * 60)
    print("OpenAlex Crosswalk Generator")
    print("=" * 60)

    # Search for journals (sources)
    print("\n--- Searching for Journals (Sources) ---")
    for journal in JOURNALS:
        print(f"\nSearching: {journal}")
        matches = search_openalex("sources", journal)

        entry = {
            "our_name": journal,
            "matches": [],
            "best_match": None,
        }

        for match in matches:
            info = extract_source_info(match)
            entry["matches"].append(info)
            print(f"  -> {info['display_name']} (ID: {info['openalex_id']}, Works: {info['works_count']})")

        if matches:
            entry["best_match"] = extract_source_info(matches[0])
        else:
            print("  -> No matches found")

        results["journals"].append(entry)
        time.sleep(0.1)  # Rate limiting

    # Search for institutions
    print("\n--- Searching for Institutions ---")
    for institution in INSTITUTIONS:
        print(f"\nSearching: {institution}")
        matches = search_openalex("institutions", institution)

        entry = {
            "our_name": institution,
            "matches": [],
            "best_match": None,
        }

        for match in matches:
            info = extract_institution_info(match)
            entry["matches"].append(info)
            print(f"  -> {info['display_name']} (ID: {info['openalex_id']}, Works: {info['works_count']})")

        if matches:
            entry["best_match"] = extract_institution_info(matches[0])
        else:
            print("  -> No matches found")

        results["institutions"].append(entry)
        time.sleep(0.1)  # Rate limiting

    # Search for publishers
    print("\n--- Searching for Publishers ---")
    for publisher in PUBLISHERS:
        print(f"\nSearching: {publisher}")
        matches = search_openalex("publishers", publisher)

        entry = {
            "our_name": publisher,
            "matches": [],
            "best_match": None,
        }

        for match in matches:
            info = extract_publisher_info(match)
            entry["matches"].append(info)
            print(f"  -> {info['display_name']} (ID: {info['openalex_id']}, Works: {info['works_count']})")

        if matches:
            entry["best_match"] = extract_publisher_info(matches[0])
        else:
            print("  -> No matches found")

        results["publishers"].append(entry)
        time.sleep(0.1)  # Rate limiting

    return results


def save_results(results: dict, output_dir: Path):
    """Save results to JSON and CSV files."""

    # Save full JSON results
    json_path = output_dir / "openalex_crosswalk_full.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nFull results saved to: {json_path}")

    # Save CSV crosswalk (best matches only)
    csv_path = output_dir / "openalex_crosswalk.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category", "our_name", "openalex_id", "openalex_name",
            "works_count", "additional_id", "match_status"
        ])

        # Journals
        for entry in results["journals"]:
            if entry["best_match"]:
                writer.writerow([
                    "journal",
                    entry["our_name"],
                    entry["best_match"]["openalex_id"],
                    entry["best_match"]["display_name"],
                    entry["best_match"]["works_count"],
                    entry["best_match"]["issn_l"] or "",
                    entry["best_match"]["alternate_names"] or "",
                    "matched",
                ])
            else:
                writer.writerow([
                    "journal",
                    entry["our_name"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "not_found",
                ])

        # Institutions
        for entry in results["institutions"]:
            if entry["best_match"]:
                writer.writerow([
                    "institution",
                    entry["our_name"],
                    entry["best_match"]["openalex_id"],
                    entry["best_match"]["display_name"],
                    entry["best_match"]["works_count"],
                    entry["best_match"]["ror"] or "",
                    entry["best_match"]["alternate_names"] or "",
                    "matched",
                ])
            else:
                writer.writerow([
                    "institution",
                    entry["our_name"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "not_found",
                ])

        # Publishers
        for entry in results["publishers"]:
            if entry["best_match"]:
                writer.writerow([
                    "publisher",
                    entry["our_name"],
                    entry["best_match"]["openalex_id"],
                    entry["best_match"]["display_name"],
                    entry["best_match"]["works_count"],
                    entry["best_match"]["alternate_names"] or "",
                    "",
                    "matched",
                ])
            else:
                writer.writerow([
                    "publisher",
                    entry["our_name"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "not_found",
                ])

    print(f"CSV crosswalk saved to: {csv_path}")


def main():
    # Set up paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    output_dir = project_dir / "rawdata"
    output_dir.mkdir(exist_ok=True)

    # Create crosswalk
    results = create_crosswalk()

    # Save results
    save_results(results, output_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    journals_matched = sum(1 for j in results["journals"] if j["best_match"])
    institutions_matched = sum(1 for i in results["institutions"] if i["best_match"])
    publishers_matched = sum(1 for p in results["publishers"] if p["best_match"])

    print(f"Journals:     {journals_matched}/{len(results['journals'])} matched")
    print(f"Institutions: {institutions_matched}/{len(results['institutions'])} matched")
    print(f"Publishers:   {publishers_matched}/{len(results['publishers'])} matched")


if __name__ == "__main__":
    main()
