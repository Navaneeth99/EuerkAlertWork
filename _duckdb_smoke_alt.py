from pathlib import Path
import duckdb

sql_path = Path("code/utils/scope_name_text_search.sql")
t = sql_path.read_text(encoding="utf-8")
ph = "{{OPENALEX_ALTERNATE_TITLES_JSON}}"
print("placeholder_count", t.count(ph))
idx = t.lower().find("openalex_alternate")
if idx < 0:
    idx = t.find("OPENALEX_ALTERNATE")
print("---SQL around alts---")
print(t[max(0, idx - 400) : idx + 900] if idx >= 0 else "NOT FOUND")

# matching_pipeline snippet
mp = Path("code/utils/matching_pipeline.py").read_text(encoding="utf-8")
i = mp.find("OPENALEX_ALTERNATE_TITLES_JSON")
print("---matching_pipeline---")
print(mp[max(0, i - 200) : i + 250])

p = Path("rawdata/Institution_OpenAlexCrossWalk/openalex_alternate_titles.json").resolve().as_posix()
print("json_path", p)
print("json_exists", Path(p).exists())
con = duckdb.connect()

# Attempt 1: user's first query style
q1 = f"""
SELECT count(*) FROM (
  SELECT category, original_name, unnest(alternate_titles) AS alt
  FROM read_json('{p}', format='array', auto_detect=true)
  WHERE alt IS NOT NULL AND length(trim(CAST(alt AS VARCHAR))) > 0
)
"""
try:
    n = con.execute(q1).fetchone()[0]
    print("ATTEMPT1 OK alt rows", n)
except Exception as e:
    print("ATTEMPT1 FAIL", type(e).__name__, e)

# Attempt 2: FROM + unnest alias
q2 = f"""
SELECT count(*) FROM (
  SELECT category, original_name, alt
  FROM read_json('{p}', format='array', auto_detect=true) AS t, unnest(t.alternate_titles) AS u(alt)
  WHERE alt IS NOT NULL AND length(trim(CAST(alt AS VARCHAR))) > 0
)
"""
try:
    n = con.execute(q2).fetchone()[0]
    print("ATTEMPT2 OK alt rows", n)
except Exception as e:
    print("ATTEMPT2 FAIL", type(e).__name__, e)

# Attempt 3: CROSS JOIN UNNEST
q3 = f"""
SELECT count(*) FROM (
  SELECT t.category, t.original_name, u.alt
  FROM read_json('{p}', format='array', auto_detect=true) AS t
  CROSS JOIN UNNEST(t.alternate_titles) AS u(alt)
  WHERE u.alt IS NOT NULL AND length(trim(CAST(u.alt AS VARCHAR))) > 0
)
"""
try:
    n = con.execute(q3).fetchone()[0]
    print("ATTEMPT3 OK alt rows", n)
except Exception as e:
    print("ATTEMPT3 FAIL", type(e).__name__, e)

# Attempt 4: list_transform / UNNEST in SELECT list
q4 = f"""
SELECT count(*) FROM (
  SELECT category, original_name, unnest(alternate_titles) AS alt
  FROM read_json('{p}', format='array', auto_detect=true)
) WHERE alt IS NOT NULL AND length(trim(CAST(alt AS VARCHAR))) > 0
"""
try:
    n = con.execute(q4).fetchone()[0]
    print("ATTEMPT4 OK alt rows", n)
except Exception as e:
    print("ATTEMPT4 FAIL", type(e).__name__, e)

# Union test with working syntax - discover which worked
working = None
for name, q in [("2", q2), ("3", q3), ("4", q4)]:
    try:
        con.execute(q).fetchone()
        working = name
        break
    except Exception:
        pass

if working == "2":
    alts_sql = f"""
      SELECT category AS entity_category, original_name AS canonical_name, CAST(alt AS VARCHAR) AS search_name
      FROM read_json('{p}', format='array', auto_detect=true) AS t, unnest(t.alternate_titles) AS u(alt)
      WHERE alt IS NOT NULL AND length(trim(CAST(alt AS VARCHAR))) > 0
    """
elif working == "3":
    alts_sql = f"""
      SELECT t.category AS entity_category, t.original_name AS canonical_name, CAST(u.alt AS VARCHAR) AS search_name
      FROM read_json('{p}', format='array', auto_detect=true) AS t
      CROSS JOIN UNNEST(t.alternate_titles) AS u(alt)
      WHERE u.alt IS NOT NULL AND length(trim(CAST(u.alt AS VARCHAR))) > 0
    """
elif working == "4":
    alts_sql = f"""
      SELECT category AS entity_category, original_name AS canonical_name, CAST(alt AS VARCHAR) AS search_name
      FROM (
        SELECT category, original_name, unnest(alternate_titles) AS alt
        FROM read_json('{p}', format='array', auto_detect=true)
      )
      WHERE alt IS NOT NULL AND length(trim(CAST(alt AS VARCHAR))) > 0
    """
else:
    alts_sql = None
    print("NO WORKING UNNEST SYNTAX")

if alts_sql:
    q_union = f"""
    WITH manual AS (
      SELECT * FROM (VALUES ('journal','Research','Research')) t(entity_category,canonical_name,search_name)
    ),
    alts AS (
      {alts_sql}
    )
    SELECT count(*) FROM (SELECT * FROM manual UNION SELECT * FROM alts)
    """
    try:
        n2 = con.execute(q_union).fetchone()[0]
        print("UNION OK rows", n2, "via attempt", working)
    except Exception as e:
        print("UNION FAIL", type(e).__name__, e)

# Peek schema
try:
    print("---describe---")
    print(con.execute(f"DESCRIBE SELECT * FROM read_json('{p}', format='array', auto_detect=true) LIMIT 1").fetchall())
    print(con.execute(f"SELECT category, original_name, alternate_titles FROM read_json('{p}', format='array', auto_detect=true) LIMIT 2").fetchall())
except Exception as e:
    print("DESCRIBE FAIL", e)
