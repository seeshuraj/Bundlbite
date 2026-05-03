# scraper/debug_zomato_search_result.py
# Drill into SECTION_SEARCH_RESULT from zomato_real.json
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_search_result.py

import json

with open("zomato_real.json", encoding="utf-8") as f:
    data = json.load(f)

sections = data["page_data"]["sections"]["SECTION_SEARCH_RESULT"]
print(f"SECTION_SEARCH_RESULT: {len(sections)} items\n")

for i, section in enumerate(sections):
    print(f"--- Result [{i}] ---")
    print(f"  type  : {section.get('type')}")
    print(f"  title : {section.get('title')}")
    items = section.get("items", [])
    print(f"  items : {len(items)}")
    if items and isinstance(items[0], dict):
        print(f"  first item keys: {list(items[0].keys())[:12]}")
        # Nested restaurant info
        item = items[0]
        # Zomato wraps in 'info' or 'restaurant' or directly
        info = item.get("info") or item.get("restaurant") or item
        name = (
            info.get("name") or info.get("resName")
            or item.get("name") or item.get("resName") or ""
        )
        rid = (
            info.get("id") or info.get("resId")
            or item.get("id") or item.get("resId") or ""
        )
        if name or rid:
            print(f"  *** name='{name}'  id='{rid}'")
        print(f"  full first item:\n{json.dumps(items[0], indent=2)[:800]}")
    print()

# Also dump showMoreData of first non-empty section
for section in sections:
    smd = section.get("showMoreData")
    if smd:
        print(f"\nshowMoreData keys: {list(smd.keys()) if isinstance(smd, dict) else type(smd)}")
        print(json.dumps(smd)[:400])
        break

print("[DONE]")
