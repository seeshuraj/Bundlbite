# scraper/debug_zomato.py
# Run this standalone to discover working Zomato API endpoints
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato.py

import asyncio
import sys
import json
import httpx

LAT, LNG = 12.9352, 77.6245
KEYWORD   = "biryani"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.zomato.com/",
    "Origin": "https://www.zomato.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


async def main():
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        verify=True,
    ) as client:

        # ── Step 1: homepage + cookies ─────────────────────────────────────────
        print("[1] Hitting Zomato homepage...")
        r0 = await client.get("https://www.zomato.com", headers=HEADERS)
        print(f"[1] Status: {r0.status_code}")
        cookies = dict(client.cookies)
        csrf = cookies.get("csrft", "")
        print(f"[1] Cookies keys: {list(cookies.keys())}")
        print(f"[1] CSRF token: '{csrf}'")
        if csrf:
            API_HEADERS["x-zomato-csrft"] = csrf

        # ── Step 2: city/location resolve ──────────────────────────────────────
        print("\n[2] Resolving city for lat/lng...")
        city_url = f"https://www.zomato.com/webroutes/location/fetch?lat={LAT}&lng={LNG}"
        r1 = await client.get(city_url, headers=API_HEADERS)
        print(f"[2] Status: {r1.status_code}")
        try:
            city_data = r1.json()
            print(f"[2] Keys: {list(city_data.keys())}")
            # Try to extract city name
            city = (
                city_data.get("city", {}).get("name")
                or city_data.get("location", {}).get("city_name")
                or "bangalore"
            )
            print(f"[2] City resolved: {city}")
        except Exception as e:
            print(f"[2] Parse error: {e} | Raw: {r1.text[:300]}")
            city = "bangalore"

        # ── Step 3: delivery listing (webroutes) ───────────────────────────────
        print("\n[3] Trying webroutes delivery endpoint...")
        urls_to_try = [
            f"https://www.zomato.com/webroutes/getPage?page_url=/{city}/order&location=&isMobile=0",
            f"https://www.zomato.com/{city.lower()}/order",
        ]
        for url in urls_to_try:
            r2 = await client.get(url, headers=API_HEADERS)
            print(f"    {url[:70]}... → {r2.status_code}")
            if r2.status_code == 200:
                ctype = r2.headers.get("content-type", "")
                print(f"    Content-Type: {ctype}")
                if "json" in ctype:
                    try:
                        d = r2.json()
                        print(f"    JSON keys: {list(d.keys())[:8]}")
                        with open("zomato_listing_raw.json", "w", encoding="utf-8") as f:
                            json.dump(d, f, indent=2, ensure_ascii=False)
                        print("    Saved → zomato_listing_raw.json")
                    except Exception as e:
                        print(f"    Parse error: {e}")
                break

        # ── Step 4: search webroute ────────────────────────────────────────────
        print("\n[4] Trying webroutes search endpoint...")
        search_urls = [
            f"https://www.zomato.com/webroutes/search/autoSuggest?q={KEYWORD}&lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/search?q={KEYWORD}&lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/getPage?page_url=/{city}/order?query={KEYWORD}&isMobile=0",
        ]
        for url in search_urls:
            r3 = await client.get(url, headers=API_HEADERS)
            print(f"    {url[:80]}... → {r3.status_code}")
            if r3.status_code == 200:
                ctype = r3.headers.get("content-type", "")
                if "json" in ctype:
                    try:
                        d = r3.json()
                        print(f"    JSON keys: {list(d.keys())[:8]}")
                        with open("zomato_search_raw.json", "w", encoding="utf-8") as f:
                            json.dump(d, f, indent=2, ensure_ascii=False)
                        print("    Saved → zomato_search_raw.json")
                    except Exception as e:
                        print(f"    Parse error: {e}")

        # ── Step 5: try the food ordering page directly ────────────────────────
        print("\n[5] Trying direct food ordering page for JSON interception...")
        order_urls = [
            f"https://www.zomato.com/webroutes/getPage?page_url=/order&lat={LAT}&lng={LNG}&isMobile=0",
            f"https://www.zomato.com/webroutes/getPage?page_url=/bangalore/order&isMobile=0",
            f"https://www.zomato.com/webroutes/getPage?page_url=/online-delivery/bangalore&isMobile=0",
        ]
        for url in order_urls:
            r4 = await client.get(url, headers=API_HEADERS)
            print(f"    {url[:80]}... → {r4.status_code}")
            if r4.status_code == 200:
                ctype = r4.headers.get("content-type", "")
                print(f"    Content-Type: {ctype}")
                if "json" in ctype:
                    try:
                        d = r4.json()
                        print(f"    JSON keys: {list(d.keys())[:10]}")
                        # Dig for restaurant data
                        sections = d.get("page", {}).get("sections", {})
                        if sections:
                            print(f"    Sections keys: {list(sections.keys())[:8]}")
                        with open("zomato_raw.json", "w", encoding="utf-8") as f:
                            json.dump(d, f, indent=2, ensure_ascii=False)
                        print("    Saved → zomato_raw.json")
                    except Exception as e:
                        print(f"    Parse error: {e}")
                break

        # ── Step 6: lat/lng based restaurant fetch ─────────────────────────────
        print("\n[6] Trying lat/lng restaurant fetch endpoints...")
        ll_urls = [
            f"https://www.zomato.com/webroutes/getPage?page_url=%2F{city}%2Forder&isMobile=0",
            f"https://www.zomato.com/webroutes/user/food/resPage?resId=18973",  # known Swiggy restaurant
        ]
        for url in ll_urls:
            r5 = await client.get(url, headers=API_HEADERS)
            print(f"    {url[:80]}... → {r5.status_code} | {r5.headers.get('content-type','')[:40]}")
            if r5.status_code == 200 and "json" in r5.headers.get("content-type", ""):
                try:
                    d5 = r5.json()
                    print(f"    Keys: {list(d5.keys())[:8]}")
                    with open("zomato_page_raw.json", "w", encoding="utf-8") as f:
                        json.dump(d5, f, indent=2, ensure_ascii=False)
                    print("    Saved → zomato_page_raw.json")
                except Exception as e:
                    print(f"    Parse: {e}")

        print("\n[DONE] Check zomato_raw.json / zomato_listing_raw.json / zomato_search_raw.json")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
