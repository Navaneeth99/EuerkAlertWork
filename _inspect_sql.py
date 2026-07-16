from pathlib import Path
t = Path("code/utils/scope_name_text_search.sql").read_text(encoding="utf-8")
ph = "{{OPENALEX_ALTERNATE_TITLES_JSON}}"
positions = []
start = 0
while True:
    i = t.find(ph, start)
    if i < 0:
        break
    positions.append(i)
    start = i + 1
print("positions", positions)
for i, pos in enumerate(positions):
    print(f"\n===== occurrence {i+1} at {pos} =====")
    print(t[max(0,pos-150):pos+len(ph)+100])

# find openalex_alternate_variations / name_variations
for key in ["openalex_alternate_variations", "name_variations", "read_json", "UNNEST", "unnest"]:
    print(f"\n{key} count:", t.lower().count(key.lower()) if key != "UNNEST" else t.count("UNNEST") + t.count("unnest"))

idx = t.find("openalex_alternate_variations")
if idx < 0:
    # find read_json block
    idx = t.find("read_json")
print("\n===== CTE BLOCK =====")
print(t[idx-100 if idx>100 else 0 : idx+1200] if idx>=0 else "missing")
