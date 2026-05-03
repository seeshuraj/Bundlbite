# scraper/debug_zomato_sections.py
# Run after debug_zomato_v4.py has saved zomato_real.json
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_sections.py

import json
import sys


def main():
    with open("zomato_real.json", encoding="utf-8") as f:
        data = json.load(f)

    sections = data["page_data"]["sections"]
    print(f"Sections type: {type(sections).__name__}")
    print(f"Sections keys: {list(sections.keys())}\n")

    for sec_key, sec_val in sections.items():
        print(f"{'='*60}")
        print(f"SECTION: {sec_key}")
        if isinstance(sec_val, dict):
            print(f"  keys: {list(sec_val.keys())[:12]}")
            # Look for restaurant lists
            for k, v in sec_val.items():
                if isinstance(v, list):
                    print(f"  [{k}] list len={len(v)}")
                    if v and isinstance(v[0], dict):
                        fk = list(v[0].keys())[:10]
                        print(f"    first item keys: {fk}")
                        # Check if restaurant
                        name = (
                            v[0].get("name")
                            or v[0].get("resName")
                            or v[0].get("restaurant", {}).get("name", "")
                            or v[0].get("info", {}).get("name", "")
                        )
                        if name:
                            print(f"    *** RESTAURANT name='{name}'")
                            print(f"    full first item: {json.dumps(v[0])[:400]}")
                        else:
                            print(f"    first item sample: {json.dumps(v[0])[:300]}")
                elif isinstance(v, dict):
                    print(f"  [{k}] dict keys={list(v.keys())[:8]}")
                    # recurse one level
                    for kk, vv in v.items():
                        if isinstance(vv, list) and vv:
                            print(f"    [{kk}] list len={len(vv)}")
                            if isinstance(vv[0], dict):
                                fk2 = list(vv[0].keys())[:10]
                                print(f"      first keys: {fk2}")
                                name2 = (
                                    vv[0].get("name")
                                    or vv[0].get("resName")
                                    or vv[0].get("info", {}).get("name", "")
                                )
                                if name2:
                                    print(f"      *** RESTAURANT name='{name2}'")
                                    print(f"      full: {json.dumps(vv[0])[:500]}")
        elif isinstance(sec_val, list):
            print(f"  list len={len(sec_val)}")
            if sec_val and isinstance(sec_val[0], dict):
                print(f"  first keys: {list(sec_val[0].keys())[:10]}")
                name = sec_val[0].get("name") or sec_val[0].get("resName")
                if name:
                    print(f"  *** RESTAURANT name='{name}'")
                    print(f"  full: {json.dumps(sec_val[0])[:400]}")
        else:
            print(f"  value: {str(sec_val)[:100]}")

    # Also check entities
    print(f"\n{'='*60}")
    print("ENTITIES:")
    entities = data.get("entities", [])
    print(f"  type={type(entities).__name__} len={len(entities) if isinstance(entities, list) else 'N/A'}")
    if isinstance(entities, dict):
        print(f"  keys: {list(entities.keys())[:10]}")
        for k, v in entities.items():
            if isinstance(v, list) and v:
                print(f"  [{k}] len={len(v)} first keys={list(v[0].keys())[:8] if isinstance(v[0], dict) else ''}")
                if isinstance(v[0], dict):
                    name = v[0].get("name") or v[0].get("resName")
                    if name:
                        print(f"  *** RESTAURANT: {name}")
                        print(f"  full: {json.dumps(v[0])[:500]}")
    elif isinstance(entities, list) and entities:
        print(f"  first: {json.dumps(entities[0])[:300]}")

    print("\n[DONE]")


if __name__ == "__main__":
    main()
