# scraper/debug_zomato_v3.py
# Fix: remove Accept-Encoding so httpx auto-decompresses.
# Use real cookies from homepage (PHPSESSID, csrf, zl, fbcity)
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_v3.py

import asyncio
import sys
import json
import httpx

LAT, LNG  = 12.9352, 77.6245
KEYWORD   = "biryani"

# NO Accept-Encoding — let httpx handle decompression automatically
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Referer": "https://www.zomato.com/bangalore/online-delivery",
    "Origin": "https://www.zomato.com",
    "Connection": "keep-alive",
}


def safe_json(r: httpx.Response, label: str) -> dict | None:
    """Decode response safely, trying multiple approaches."""
    # Try httpx built-in (handles brotli/gzip if httpx[brotli] installed)
    try:
        return r.json()
    except Exception:
        pass
    # Try decoding raw bytes as utf-8 with errors ignored
    try:
        text = r.content.decode("utf-8", errors="replace")
        return json.loads(text)
    except Exception:
        pass
    # Try latin-1
    try:
        text = r.content.decode("latin-1")
        return json.loads(text)
    except Exception:
        pass
    # Try decompressing manually
    try:
        import gzip
        text = gzip.decompress(r.content).decode("utf-8")
        return json.loads(text)
    except Exception:
        pass
    try:
        import brotli  # pip install brotli
        text = brotli.decompress(r.content).decode("utf-8")
        return json.loads(text)
    except Exception:
        pass
    # Save raw bytes for manual inspection
    with open(f"zomato_raw_{label}.bin", "wb") as f:
        f.write(r.content)
    print(f"  Saved raw bytes -> zomato_raw_{label}.bin  ({len(r.content)} bytes)")
    print(f"  Content-Encoding: {r.headers.get('content-encoding', 'none')}")
    print(f"  First 20 bytes hex: {r.content[:20].hex()}")
    return None


async def main():
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        headers={},   # No default headers — set per request
    ) as client:

        # ─ Step 1: get real cookies from Zomato homepage ─────────────────────
        print("[1] Getting cookies from homepage...")
        r0 = await client.get("https://www.zomato.com", headers=BROWSER_HEADERS)
        print(f"[1] Status: {r0.status_code}")
        cookies = dict(client.cookies)
        print(f"[1] Cookies: {list(cookies.keys())}")
        csrf   = cookies.get("csrf", "")     # note: key is 'csrf' not 'csrft'
        zl_val = cookies.get("zl", "")
        print(f"[1] csrf='{csrf}'  zl='{zl_val[:60]}'")

        # Add CSRF to API headers
        if csrf:
            API_HEADERS["x-zomato-csrft"] = csrf

        # ─ Step 2: hit food ordering page to trigger geo cookies ──────────────
        print("\n[2] Triggering geo session on food page...")
        r1 = await client.get(
            "https://www.zomato.com/bangalore/online-delivery",
            headers=BROWSER_HEADERS
        )
        print(f"[2] Status: {r1.status_code} | URL: {r1.url}")
        cookies2 = dict(client.cookies)
        print(f"[2] Cookies now: {list(cookies2.keys())}")

        # ─ Step 3: webroutes with decompression ───────────────────────────
        print("\n[3] Hitting webroutes (with decompression fix)...")
        webroutes = [
            "https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fonline-delivery&isMobile=0",
            "https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fonline-delivery%2Fbiryani-restaurants&isMobile=0",
        ]
        for url in webroutes:
            r = await client.get(url, headers=API_HEADERS)
            print(f"   {url[50:90]}... -> {r.status_code}")
            print(f"   Content-Encoding: {r.headers.get('content-encoding', 'none')}")
            print(f"   Content-Type: {r.headers.get('content-type', '')}")
            d = safe_json(r, "webroute")
            if d:
                pd = d.get("page_data", {})
                fsd = pd.get("firstSectionData", {})
                if "can't seem" in str(fsd.get("text", "")):
                    print("   -> Fake 200: still 404 page")
                else:
                    print(f"   -> REAL DATA! page_data keys: {list(pd.keys())[:10]}")
                    sections = pd.get("sections", {})
                    if sections:
                        print(f"   sections keys: {list(sections.keys())[:10]}")
                    entities = d.get("entities", [])
                    print(f"   entities len: {len(entities) if isinstance(entities, list) else type(entities)}")
                    with open("zomato_food_v3.json", "w", encoding="utf-8") as f:
                        json.dump(d, f, indent=2, ensure_ascii=False)
                    print("   Saved -> zomato_food_v3.json")

        # ─ Step 4: autoSuggest with decompression ──────────────────────────
        print("\n[4] autoSuggest with decompression fix...")
        rs = await client.get(
            f"https://www.zomato.com/webroutes/search/autoSuggest?q={KEYWORD}&lat={LAT}&lng={LNG}",
            headers=API_HEADERS
        )
        print(f"[4] Status: {rs.status_code}")
        print(f"[4] Content-Encoding: {rs.headers.get('content-encoding', 'none')}")
        ds = safe_json(rs, "suggest")
        if ds:
            print(f"[4] Keys: {list(ds.keys())}")
            results = ds.get("results", {})
            if isinstance(results, dict):
                for k, v in results.items():
                    if isinstance(v, list) and v:
                        print(f"   results.{k}: list len={len(v)}")
                        print(f"   first item: {json.dumps(v[0])[:300]}")
                    elif isinstance(v, list):
                        print(f"   results.{k}: empty list")
                    else:
                        print(f"   results.{k}: {str(v)[:100]}")
            elif isinstance(results, list):
                print(f"[4] results len: {len(results)}")
                if results:
                    print(f"   first: {json.dumps(results[0])[:300]}")
            with open("zomato_suggest_v3.json", "w", encoding="utf-8") as f:
                json.dump(ds, f, indent=2, ensure_ascii=False)
            print("[4] Saved -> zomato_suggest_v3.json")

        # ─ Step 5: install brotli check ───────────────────────────────────
        print("\n[5] Checking brotli support...")
        try:
            import brotli
            print("[5] brotli: INSTALLED")
        except ImportError:
            print("[5] brotli: NOT installed -> run: pip install brotli")
        try:
            import httpx
            print(f"[5] httpx version: {httpx.__version__}")
        except Exception:
            pass

        print("\n[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
