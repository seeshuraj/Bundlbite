# scraper/debug_zomato_parse.py
# Run AFTER debug_zomato.py has saved zomato_raw.json and zomato_listing_raw.json
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_parse.py

import json
import sys


def dig(obj, path="root", depth=0, max_depth=6):
    """Recursively print structure, stopping at max_depth or when we find restaurants."""
    indent = "  " * depth
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > 0:
                print(f"{indent}[LIST] {path}.{k}  len={len(v)}")
                # Print first item keys if it's a dict
                if isinstance(v[0], dict):
                    print(f"{indent}  first item keys: {list(v[0].keys())[:10]}")
                    # If looks like a restaurant, print name
                    name = v[0].get("name") or v[0].get("resName") or v[0].get("restaurant", {}).get("name")
                    if name:
                        print(f"{indent}  *** RESTAURANT? name='{name}'")
                    # Recurse one level into first item
                    dig(v[0], f"{path}.{k}[0]", depth + 1, max_depth)
            elif isinstance(v, dict) and v:
                print(f"{indent}[DICT] {path}.{k}  keys={list(v.keys())[:8]}")
                dig(v, f"{path}.{k}", depth + 1, max_depth)
            else:
                if isinstance(v, str) and len(v) < 80:
                    print(f"{indent}  {k}: {v!r}")
    elif isinstance(obj, list) and obj:
        dig(obj[0], f"{path}[0]", depth, max_depth)


def inspect_file(fname):
    print(f"\n{'='*60}")
    print(f"INSPECTING: {fname}")
    print('='*60)
    try:
        with open(fname, encoding="utf-8") as f:
            data = json.load(f)
        print(f"Top-level keys: {list(data.keys())}")

        # Focus on page_data and entities — that's where Zomato puts restaurants
        for focus_key in ["page_data", "entities", "sections"]:
            if focus_key in data:
                v = data[focus_key]
                print(f"\n--- {focus_key} (type={type(v).__name__}) ---")
                if isinstance(v, dict):
                    print(f"  keys: {list(v.keys())[:15]}")
                    dig(v, focus_key, depth=1, max_depth=5)
                elif isinstance(v, list):
                    print(f"  len={len(v)}")
                    if v:
                        print(f"  first keys: {list(v[0].keys())[:10] if isinstance(v[0], dict) else v[0]}")
                        dig(v[0], f"{focus_key}[0]", depth=1, max_depth=5)

        # Also check for any key that has 'restaurant' in its name
        print("\n--- Scanning for 'restaurant' keys anywhere in top level ---")
        def find_restaurants(obj, path="", depth=0):
            if depth > 8:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_path = f"{path}.{k}"
                    if "restaurant" in str(k).lower() or "restorant" in str(k).lower():
                        print(f"  FOUND: {new_path}  type={type(v).__name__}  ", end="")
                        if isinstance(v, list):
                            print(f"len={len(v)}")
                            if v and isinstance(v[0], dict):
                                print(f"    first keys: {list(v[0].keys())[:8]}")
                                name = v[0].get("name") or v[0].get("resName")
                                if name:
                                    print(f"    first name: {name}")
                        elif isinstance(v, dict):
                            print(f"keys={list(v.keys())[:6]}")
                        else:
                            print(str(v)[:60])
                    find_restaurants(v, new_path, depth + 1)
            elif isinstance(obj, list):
                for i, item in enumerate(obj[:3]):
                    find_restaurants(item, f"{path}[{i}]", depth + 1)

        find_restaurants(data)

    except FileNotFoundError:
        print(f"  File not found: {fname}")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    inspect_file("zomato_raw.json")
    inspect_file("zomato_listing_raw.json")
    inspect_file("zomato_search_raw.json")
    print("\n[DONE]")
