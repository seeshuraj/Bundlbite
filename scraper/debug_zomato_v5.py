# scraper/debug_zomato_v5.py
# /bangalore/delivery gives empty restaurant items without location context.
# Strategy: use dish/cuisine URLs from SECTION_CITY_MAGIC_LINKS which already
# embed location intent, OR use the zsearch API with lat/lng.
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_v5.py

import asyncio
import sys
import json
import httpx

LAT, LNG   = 12.9352, 77.6245   # Koramangala, Bangalore
CITY_ID    = 4                   # Bangalore city_id
KEYWORD    = "biryani"

BROWSER_H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile": "?0",
    "Upgrade-Insecure-Requests": "1",
}


def api_headers(csrf, referer):
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Referer": referer,
        "Origin": "https://www.zomato.com",
        "x-zomato-csrft": csrf,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def is_real(d):
    fsd = d.get("page_data", {}).get("firstSectionData", {})
    return "can't seem" not in str(fsd.get("text", ""))


def extract_restaurants(d):
    """Pull restaurant items from SECTION_SEARCH_RESULT."""
    results = []
    sections = d.get("page_data", {}).get("sections", {})
    search_result = sections.get("SECTION_SEARCH_RESULT", [])
    for sec in search_result:
        if sec.get("type") == "restaurant":
            for item in sec.get("items", []):
                info = item.get("info") or item
                results.append(info)
    return results


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:

        # Step 1: seed cookies
        print("[1] Seeding cookies...")
        await client.get("https://www.zomato.com", headers=BROWSER_H)
        await client.get("https://www.zomato.com/bangalore", headers=BROWSER_H)
        csrf = client.cookies.get("csrf", "")
        print(f"    csrf: {csrf[:16]}...")

        # Step 2: set location cookie (exact format Zomato uses)
        # Observed from browser: zl cookie contains JSON-like location data
        loc_val = (
            f"{{\"lat\":\"{LAT}\",\"lng\":\"{LNG}\","
            f"\"cityId\":\"{CITY_ID}\",\"cityName\":\"Bangalore\","
            f"\"addressId\":0,\"locality\":\"\"}}"
        )
        client.cookies.set("userLocation", loc_val, domain=".zomato.com")

        print("\n[2] Trying dish/cuisine delivery URLs (these embed location context)...")
        BASE = "https://www.zomato.com/webroutes/getPage?page_url="
        dish_paths = [
            "%2Fbangalore%2Fdelivery%2Fdish-biryani",
            "%2Fbangalore%2Fdelivery%2Fdish-chicken-biryani",
            "%2Fbangalore%2Fdelivery%2Fdish-pizza",
            "%2Fbangalore%2Fdelivery%2Fdish-burger",
        ]

        for path in dish_paths:
            url = f"{BASE}{path}&isMobile=0"
            h = api_headers(csrf, f"https://www.zomato.com/bangalore/delivery")
            r = await client.get(url, headers=h)
            enc = r.headers.get("content-encoding", "none")
            print(f"   {r.status_code} [{enc}]  <- {path[20:]}")
            try:
                d = r.json()
            except Exception:
                print("   [parse error]")
                continue
            if not is_real(d):
                print("   -> fake-200")
                continue
            rests = extract_restaurants(d)
            print(f"   -> REAL! restaurants extracted: {len(rests)}")
            if rests:
                print(f"   first: {json.dumps(rests[0])[:400]}")
                with open("zomato_dish.json", "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                print("   Saved -> zomato_dish.json")
                break
            else:
                # Dump all section types to understand structure
                sr = d.get("page_data", {}).get("sections", {}).get("SECTION_SEARCH_RESULT", [])
                types = [(s.get("type"), len(s.get("items", []))) for s in sr]
                print(f"   sections: {types}")
                with open("zomato_dish_empty.json", "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
                print("   Saved -> zomato_dish_empty.json (inspect manually)")
                break

        # Step 3: zsearch API (what the browser actually calls for listings)
        print("\n[3] Trying zsearch/search API...")
        zsearch_urls = [
            f"https://www.zomato.com/webroutes/search/query?q={KEYWORD}&lat={LAT}&lng={LNG}&category=delivery&city_id={CITY_ID}&restaurant_type=Delivery",
            f"https://www.zomato.com/webroutes/search/query?q=&lat={LAT}&lng={LNG}&category=delivery&city_id={CITY_ID}",
            f"https://www.zomato.com/webroutes/city/delivery?lat={LAT}&lng={LNG}&city_id={CITY_ID}",
        ]
        for url in zsearch_urls:
            h = api_headers(csrf, "https://www.zomato.com/bangalore/delivery")
            r = await client.get(url, headers=h)
            enc = r.headers.get("content-encoding", "none")
            print(f"   {r.status_code} [{enc}]  <- {url[40:90]}")
            if r.status_code == 200:
                try:
                    d = r.json()
                    print(f"   keys: {list(d.keys())[:8]}")
                    with open("zomato_zsearch.json", "w", encoding="utf-8") as f:
                        json.dump(d, f, indent=2, ensure_ascii=False)
                    print("   Saved -> zomato_zsearch.json")
                    break
                except Exception as e:
                    print(f"   parse error: {e}")

        # Step 4: getPage with lat/lng as query params (not encoded in page_url)
        print("\n[4] getPage with lat/lng query params directly...")
        direct_urls = [
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fdelivery&isMobile=0&lat={LAT}&lng={LNG}",
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fdelivery&isMobile=0&cityId={CITY_ID}&lat={LAT}&lng={LNG}",
        ]
        for url in direct_urls:
            h = api_headers(csrf, "https://www.zomato.com/bangalore/delivery")
            r = await client.get(url, headers=h)
            print(f"   {r.status_code}  <- {url[50:110]}")
            if r.status_code == 200:
                try:
                    d = r.json()
                    if is_real(d):
                        rests = extract_restaurants(d)
                        print(f"   restaurants: {len(rests)}")
                        if rests:
                            print(f"   *** GOT RESTAURANTS: {json.dumps(rests[0])[:300]}")
                            with open("zomato_latlong.json", "w", encoding="utf-8") as f:
                                json.dump(d, f, indent=2, ensure_ascii=False)
                            print("   Saved -> zomato_latlong.json")
                except Exception:
                    pass

        print("\n[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
