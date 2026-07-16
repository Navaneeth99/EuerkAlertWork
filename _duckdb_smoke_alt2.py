from pathlib import Path
import duckdb
import re

sql_path = Path("code/utils/scope_name_text_search.sql")
t = sql_path.read_text(encoding="utf-8")
p = Path("rawdata/Institution_OpenAlexCrossWalk/openalex_alternate_titles.json").resolve().as_posix()
ph = "{{OPENALEX_ALTERNATE_TITLES_JSON}}"
print("placeholder_count", t.count(ph))
print("occurrences: comment + read_json path")

# Extract openalex + name_variations CTEs
m = re.search(
    r"openalex_alternate_variations AS \((.*?)\),\s*\n\s*name_variations AS \((.*?)\)\s*(?:,|\n\w)",
    t,
    re.S,
)
if not m:
    # broader extract
    i = t.find("openalex_alternate_variations AS")
    print("raw slice:")
    print(t[i:i+900])
else:
    print("=== openalex_alternate_variations ===")
    print(m.group(1)[:800])
    print("=== name_variations ===")
    print(m.group(2)[:500])

# Full smoke: replace and run only the alts CTE as a SELECT count
replaced = t.replace(ph, p)
# Pull the openalex CTE body
i = replaced.find("openalex_alternate_variations AS (")
j = replaced.find("name_variations AS (", i)
body = replaced[i + len("openalex_alternate_variations AS (") : j].rsplit("),", 1)[0]
print("=== CTE body used ===")
print(body[:700])

con = duckdb.connect()
q = f"SELECT count(*) FROM ({body})"
try:
    n = con.execute(q).fetchone()[0]
    print("CTE_SMOKE OK rows", n)
except Exception as e:
    print("CTE_SMOKE FAIL", e)

# Try full scope SQL? might need pr_base - expect fail
try:
    # Only create table part needs pr_base for later joins maybe - try execute whole
    # First check if it references pr_base in the CREATE
    if "pr_base" in replaced.lower():
        print("SQL references pr_base - skipping full execute unless view exists")
    con.execute("CREATE OR REPLACE VIEW pr_base AS SELECT 1 AS x")  # dummy may fail if schema wrong
except Exception as e:
    print("setup note", e)

# Verify matching_pipeline replace logic
mp = Path("code/utils/matching_pipeline.py").read_text(encoding="utf-8")
assert '{{OPENALEX_ALTERNATE_TITLES_JSON}}' in mp or 'OPENALEX_ALTERNATE_TITLES_JSON' in mp
# show lines around replace
for li, line in enumerate(mp.splitlines(), 1):
    if "OPENALEX_ALTERNATE" in line or "ALTERNATE_TITLES_JSON" in line and "SCOPE" not in line:
        if "replace" in line or "OPENALEX" in line or "ALTERNATE_TITLES_JSON" in line:
            print(f"pipeline:{li}:{line.strip()}")

print("DONE")
