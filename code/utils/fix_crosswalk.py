"""
Fix crosswalk matches - search with better terms for problematic entries
"""

import requests
import json
import time

BASE_URL = "https://api.openalex.org"
PARAMS = {"mailto": "research@example.com"}


def search_openalex(entity_type: str, query: str, filters: dict = None) -> list:
    """Search OpenAlex with optional filters."""
    url = f"{BASE_URL}/{entity_type}"
    params = {
        **PARAMS,
        "search": query,
        "per_page": 10,
    }
    if filters:
        filter_str = ",".join(f"{k}:{v}" for k, v in filters.items())
        params["filter"] = filter_str

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.RequestException as e:
        print(f"Error: {e}")
        return []


def get_entity_by_id(entity_type: str, entity_id: str) -> dict:
    """Get a specific entity by its OpenAlex ID."""
    url = f"{BASE_URL}/{entity_type}/{entity_id}"
    params = PARAMS.copy()

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error: {e}")
        return {}


print("=" * 70)
print("FIXING JOURNAL MATCHES")
print("=" * 70)

# 1. Intelligent Computing - we know the correct ID from earlier search
print("\n1. Intelligent Computing")
print("   Correct match found in earlier search: S4387281904")
result = get_entity_by_id("sources", "S4387281904")
if result:
    print(f"   ✓ {result.get('display_name')} (Works: {result.get('works_count')})")
    print(f"   ID: {result.get('id')}")
    print(f"   ISSN-L: {result.get('issn_l')}")
    print(f"   Host: {result.get('host_organization_name')}")

# 2. Journal of Remote Sensing - search for Science Partner version
print("\n2. Journal of Remote Sensing (Science Partner Journal)")
# Try searching with publisher filter or more specific terms
results = search_openalex("sources", "Journal of Remote Sensing")
print("   All matches:")
for r in results:
    host = r.get('host_organization_name', 'N/A')
    print(f"   - {r.get('display_name')} | Host: {host} | Works: {r.get('works_count')} | ID: {r.get('id')}")

# Also try filtering by AAAS or Science
print("\n   Searching with 'Remote Sensing AAAS':")
results2 = search_openalex("sources", "Remote Sensing Science")
for r in results2[:5]:
    host = r.get('host_organization_name', 'N/A')
    print(f"   - {r.get('display_name')} | Host: {host} | Works: {r.get('works_count')} | ID: {r.get('id')}")

# 3. Research - the Science Partner Journal
print("\n3. Research (Science Partner Journal)")
# This is tricky - "Research" is too generic. Let's search with AAAS context
results = search_openalex("sources", "Research AAAS")
print("   Searching 'Research AAAS':")
for r in results[:5]:
    host = r.get('host_organization_name', 'N/A')
    print(f"   - {r.get('display_name')} | Host: {host} | Works: {r.get('works_count')} | ID: {r.get('id')}")

# Try searching for Research with Science publisher
print("\n   Searching 'Research Science':")
results = search_openalex("sources", "Research Science")
for r in results[:5]:
    host = r.get('host_organization_name', 'N/A')
    issn = r.get('issn_l', 'N/A')
    print(f"   - {r.get('display_name')} | ISSN-L: {issn} | Host: {host} | Works: {r.get('works_count')} | ID: {r.get('id')}")

# Try direct ID lookup - the journal "Research" published by AAAS/Science China Press
# ISSN for Research journal: 2639-5274
print("\n   Searching by ISSN 2639-5274:")
results = search_openalex("sources", "2639-5274")
for r in results[:3]:
    host = r.get('host_organization_name', 'N/A')
    print(f"   - {r.get('display_name')} | Host: {host} | Works: {r.get('works_count')} | ID: {r.get('id')}")

print("\n" + "=" * 70)
print("SEARCHING FOR MISSING CAS INSTITUTES")
print("=" * 70)

# Missing CAS institutes - try shorter/alternative names
missing_institutes = [
    ("Institute of Process Engineering, CAS", ["Institute of Process Engineering", "IPE CAS", "Process Engineering Chinese Academy"]),
    ("Institute of Atmospheric Physics, CAS", ["Institute of Atmospheric Physics", "IAP Beijing", "Atmospheric Physics CAS"]),
    ("Aerospace Information Research Institute, CAS", ["Aerospace Information Research Institute", "AIR CAS", "AIRCAS"]),
    ("Dalian Institute of Chemical Physics, CAS", ["Dalian Institute of Chemical Physics", "DICP", "Dalian Chemical Physics"]),
    ("Hefei Institutes of Physical Science, CAS", ["Hefei Institutes of Physical Science", "HFIPS", "Hefei Physical Science"]),
    ("Shenzhen Institute of Advanced Technology, CAS", ["Shenzhen Institute of Advanced Technology", "SIAT", "Shenzhen Advanced Technology"]),
]

for original_name, search_terms in missing_institutes:
    print(f"\n{original_name}")
    found = False
    for term in search_terms:
        print(f"   Trying: '{term}'")
        results = search_openalex("institutions", term)
        for r in results[:3]:
            country = r.get('country_code', 'N/A')
            ror = r.get('ror', 'N/A')
            print(f"      - {r.get('display_name')} | Country: {country} | Works: {r.get('works_count')} | ID: {r.get('id')}")
            if not found and country == 'CN':
                found = True
        if found:
            break
        time.sleep(0.1)

print("\n" + "=" * 70)
print("SEARCHING FOR BEIJING INSTITUTE OF TECHNOLOGY PRESS")
print("=" * 70)

search_terms = [
    "Beijing Institute of Technology Press",
    "BIT Press",
    "Beijing Institute Technology",
]

for term in search_terms:
    print(f"\nTrying publishers: '{term}'")
    results = search_openalex("publishers", term)
    for r in results[:3]:
        print(f"   - {r.get('display_name')} | Works: {r.get('works_count')} | ID: {r.get('id')}")

# Also check if it's indexed as an institution
print("\nTrying as institution:")
results = search_openalex("institutions", "Beijing Institute of Technology")
for r in results[:3]:
    print(f"   - {r.get('display_name')} | Type: {r.get('type')} | Works: {r.get('works_count')} | ID: {r.get('id')}")
