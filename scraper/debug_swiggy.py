# scraper/debug_swiggy.py
# Run this standalone to dump the raw Swiggy API response
# Usage: python scraper/debug_swiggy.py

import asyncio
import sys
import json
import httpx

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.swiggy.com/",
    "Origin": "https://www.swiggy.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Content-Type": "application/json",
}

async def main():
    lat, lng = 12.9352, 77.6245

    async with httpx.AsyncClient(headers=BASE_HEADERS, follow_redirects=True, timeout=30) as client:
        # Get cookies
        print("[1] Hitting homepage for cookies...")
        r = await client.get("https://www.swiggy.com")
        cookies = dict(r.cookies)
        print(f"[1] Cookies: {cookies}")
        print(f"[1] Homepage status: {r.status_code}")

        # Hit API
        url = (
            f"https://www.swiggy.com/dapi/restaurants/list/v5"
            f"?lat={lat}&lng={lng}&is-seo-homepage-enabled=true"
            f"&page_type=DESKTOP_WEB_LISTING"
        )
        print(f"\n[2] Hitting API: {url}")
        r2 = await client.get(url, cookies=cookies)
        print(f"[2] Status: {r2.status_code}")
        print(f"[2] Content-Type: {r2.headers.get('content-type')}")

        try:
            data = r2.json()
            # Show top-level keys
            print(f"\n[3] Top-level keys: {list(data.keys())}")
            print(f"[3] statusCode: {data.get('statusCode')}")

            cards = data.get("data", {}).get("cards", [])
            print(f"[3] Number of cards: {len(cards)}")

            # Dump first 2 cards structure
            for i, card in enumerate(cards[:3]):
                print(f"\n--- Card {i} keys: {list(card.keys())}")
                inner = card.get("card", {}).get("card", {})
                print(f"    inner @type: {inner.get('@type', 'N/A')}")
                print(f"    inner keys: {list(inner.keys())[:10]}")

                # Check gridElements
                grid = inner.get("gridElements", {})
                if grid:
                    info = grid.get("infoWithStyle", {})
                    rests = info.get("restaurants", [])
                    print(f"    gridElements.infoWithStyle.restaurants count: {len(rests)}")
                    if rests:
                        print(f"    First restaurant keys: {list(rests[0].keys())}")
                        info_inner = rests[0].get("info", {})
                        print(f"    First restaurant name: {info_inner.get('name', 'N/A')}")

            # Save full response
            with open("swiggy_raw.json", "w") as f:
                json.dump(data, f, indent=2)
            print("\n[4] Full response saved to swiggy_raw.json")

        except Exception as e:
            print(f"[3] JSON parse error: {e}")
            print(f"[3] Raw response (first 500 chars): {r2.text[:500]}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
