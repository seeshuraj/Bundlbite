# scraper/debug_zomato_v2.py
# Second attempt: use the correct Zomato food delivery URLs
# Zomato's food ordering is at /bangalore/online-delivery or
# uses a specific webroute with location cookies set first.
# Usage: .\venv\Scripts\python.exe scraper\debug_zomato_v2.py

import asyncio
import sys
import json
import httpx

LAT, LNG   = 12.9352, 77.6245
KEYWORD    = "biryani"
CITY_ID    = 4   # Bangalore city ID on Zomato
ENTITY_ID  = 4   # Bangalore entity ID

# Full browser headers — mimic Chrome on Windows exactly
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
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
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.zomato.com/bangalore/order",
    "Origin": "https://www.zomato.com",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Connection": "keep-alive",
}


async def main():
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        http2=False,
    ) as client:

        # Step 1: hit the actual food ordering page first (not homepage)
        print("[1] Hitting Bangalore food ordering page directly...")
        r0 = await client.get(
            "https://www.zomato.com/bangalore/online-delivery",
            headers=HEADERS
        )
        print(f"[1] Status: {r0.status_code}")
        print(f"[1] Final URL: {r0.url}")
        cookies = dict(client.cookies)
        print(f"[1] Cookie keys: {list(cookies.keys())}")
        csrf = cookies.get("csrft", "")
        print(f"[1] CSRF: '{csrf}'")

        if csrf:
            API_HEADERS["x-zomato-csrft"] = csrf

        # Also set location cookies manually (Zomato uses these for geo)
        client.cookies.set("zl", f"lat%3D{LAT}%26lng%3D{LNG}%26cityId%3D4%26cityName%3DBangalore")

        # Step 2: try the correct food delivery webroute
        print("\n[2] Trying correct food delivery webroutes...")
        food_urls = [
            # The actual URL Zomato's SPA hits for food delivery listing
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fonline-delivery&isMobile=0",
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fonline-delivery%2Fbiryani-restaurants&isMobile=0",
            f"https://www.zomato.com/webroutes/getPage?page_url=%2Fbangalore%2Fonline-delivery%3Fquery%3Dbiryani&isMobile=0",
        ]
        for url in food_urls:
            r = await client.get(url, headers=API_HEADERS)
            print(f"   {url[50:90]}... -> {r.status_code}")
            if r.status_code == 200:
                try:
                    d = r.json()
                    pd = d.get("page_data", {})
                    # Check if it's the 404 page again
                    fsd = pd.get("firstSectionData", {})
                    if "can't seem" in str(fsd.get("text", "")):
                        print("   -> Still 404 page disguised as 200")
                        continue
                    print(f"   -> REAL DATA! page_data keys: {list(pd.keys())[:10]}")
                    with open("zomato_food_raw.json", "w", encoding="utf-8") as f:
                        json.dump(d, f, indent=2, ensure_ascii=False)
                    print("   Saved -> zomato_food_raw.json")
                except Exception as e:
                    print(f"   Parse error: {e}")

        # Step 3: try the search API that DID return 200 earlier
        print("\n[3] Inspecting the autoSuggest result more carefully...")
        r_suggest = await client.get(
            f"https://www.zomato.com/webroutes/search/autoSuggest?q={KEYWORD}&lat={LAT}&lng={LNG}&entityId={ENTITY_ID}&entityType=city",
            headers=API_HEADERS
        )
        print(f"[3] Status: {r_suggest.status_code}")
        if r_suggest.status_code == 200:
            d3 = r_suggest.json()
            results = d3.get("results", {})
            print(f"[3] results type: {type(results).__name__}")
            if isinstance(results, dict):
                print(f"[3] results keys: {list(results.keys())}")
                for k, v in results.items():
                    if isinstance(v, list):
                        print(f"    {k}: list len={len(v)}")
                        if v and isinstance(v[0], dict):
                            print(f"    first keys: {list(v[0].keys())[:10]}")
                            print(f"    first item: {json.dumps(v[0])[:200]}")
            elif isinstance(results, list):
                print(f"[3] results len: {len(results)}")
                if results:
                    print(f"    first: {json.dumps(results[0])[:300]}")
            with open("zomato_suggest_raw.json", "w", encoding="utf-8") as f:
                json.dump(d3, f, indent=2, ensure_ascii=False)
            print("[3] Saved -> zomato_suggest_raw.json")

        # Step 4: try the Zomato ordering API used by the mobile app
        print("\n[4] Trying Zomato mobile ordering API...")
        mobile_urls = [
            f"https://www.zomato.com/api/v2.1/search?entity_id={ENTITY_ID}&entity_type=city&q={KEYWORD}&lat={LAT}&lon={LNG}&order=desc&sort=rating&start=0&count=10",
            f"https://www.zomato.com/api/v2.1/restaurants?entity_id={ENTITY_ID}&entity_type=city&lat={LAT}&lon={LNG}&count=10",
        ]
        for url in mobile_urls:
            rm = await client.get(url, headers={
                **API_HEADERS,
                "Accept": "application/json",
            })
            print(f"   Status: {rm.status_code} | {url[40:90]}")
            if rm.status_code == 200:
                try:
                    dm = rm.json()
                    print(f"   Keys: {list(dm.keys())[:8]}")
                    rests = dm.get("restaurants", [])
                    print(f"   restaurants count: {len(rests)}")
                    if rests:
                        print(f"   first: {json.dumps(rests[0])[:300]}")
                        with open("zomato_api_raw.json", "w", encoding="utf-8") as f:
                            json.dump(dm, f, indent=2, ensure_ascii=False)
                        print("   Saved -> zomato_api_raw.json")
                except Exception as e:
                    print(f"   Error: {e}")

        print("\n[DONE]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
