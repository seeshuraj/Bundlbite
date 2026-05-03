# scraper/zomato_scraper.py
# Production Zomato scraper — uses /webroutes/search/home (POST)
# Confirmed endpoint from Playwright network interception.
#
# Usage: .\venv\Scripts\python.exe scraper\zomato_scraper.py

import asyncio
import json
import sys
import httpx

LAT     = 12.9352
LNG     = 77.6245
CITY_ID = 4          # Bangalore
PAGE_SIZE = 15       # restaurants per POST call

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def seed_headers():
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
    }


def api_headers(csrf: str, referer: str) -> dict:
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Content-Type": "application/json",
        "Referer": referer,
        "Origin": "https://www.zomato.com",
        "x-zomato-csrft": csrf,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def parse_restaurant(item: dict) -> dict | None:
    """Extract clean restaurant fields from a search/home item."""
    info = item.get("info") or item
    if not info.get("name"):
        return None

    # Rating
    rating_obj = info.get("rating", {})
    rating = (
        rating_obj.get("aggregate_rating")
        or rating_obj.get("rating")
        or ""
    )

    # Cuisine
    cuisine = ", ".join(
        c.get("deeplink_text", c.get("name", ""))
        for c in info.get("cuisine", [])
    )

    # Delivery time
    order_link = info.get("orderLink", {})
    delivery_time = (
        info.get("delivery_time")
        or info.get("deliveryTime")
        or order_link.get("deliveryTime", "")
    )

    # Price
    price = info.get("price", info.get("average_cost_for_two", ""))

    # Image
    image_obj = info.get("image", {})
    image_url = image_obj.get("url", image_obj.get("imageUrl", ""))

    # URL
    action = info.get("actionInfo", {})
    slug = action.get("clickUrl", "")
    url = f"https://www.zomato.com{slug}" if slug else ""

    return {
        "id":            str(info.get("resId", "")),
        "name":          info.get("name", ""),
        "rating":        str(rating),
        "cuisine":       cuisine,
        "delivery_time": str(delivery_time),
        "price_for_two": str(price),
        "image":         image_url,
        "url":           url,
        "source":        "zomato",
    }


async def scrape_zomato(
    keyword: str = "",
    lat: float = LAT,
    lng: float = LNG,
    max_results: int = 40,
) -> list[dict]:
    """
    Returns a list of restaurant dicts from Zomato delivery listings.
    keyword: optional cuisine/dish filter (e.g. 'biryani')
    """
    restaurants = []
    seen_ids = set()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # Step 1: seed session cookies
        await client.get("https://www.zomato.com", headers=seed_headers())
        await client.get("https://www.zomato.com/bangalore", headers=seed_headers())
        csrf = client.cookies.get("csrf", "")
        if not csrf:
            # fallback: fetch csrf directly
            r = await client.get(
                "https://www.zomato.com/webroutes/auth/csrf",
                headers=api_headers("", "https://www.zomato.com")
            )
            csrf = r.json().get("csrf", "")
        print(f"[zomato] csrf: {csrf[:16]}...")

        referer = "https://www.zomato.com/bangalore/delivery"
        h = api_headers(csrf, referer)

        # Step 2: paginate through search/home POST
        # Payload reverse-engineered from browser network capture
        page = 1
        while len(restaurants) < max_results:
            payload = {
                "lat":          lat,
                "lng":          lng,
                "cityId":       CITY_ID,
                "cuisines":     "",
                "q":            keyword,
                "context":      "delivery",
                "sortBy":       "relevance",
                "filters":      {},
                "row_offset":   (page - 1) * PAGE_SIZE,
                "rows":         PAGE_SIZE,
                "isMobile":     0,
            }

            r = await client.post(
                "https://www.zomato.com/webroutes/search/home",
                headers=h,
                json=payload,
            )

            if r.status_code != 200:
                print(f"[zomato] page {page} -> {r.status_code}, stopping.")
                break

            try:
                data = r.json()
            except Exception as e:
                print(f"[zomato] parse error page {page}: {e}")
                break

            sections = data.get("sections", {})
            sr = sections.get("SECTION_SEARCH_RESULT", [])

            # sr may be a list of individual restaurant items OR a list of sections
            batch = []
            if isinstance(sr, list):
                for item in sr:
                    if isinstance(item, dict):
                        # Direct item with info
                        if "info" in item or "resId" in item:
                            parsed = parse_restaurant(item)
                            if parsed:
                                batch.append(parsed)
                        # Section wrapper
                        elif "items" in item:
                            for sub in item.get("items", []):
                                parsed = parse_restaurant(sub)
                                if parsed:
                                    batch.append(parsed)

            new = 0
            for r_item in batch:
                if r_item["id"] not in seen_ids:
                    seen_ids.add(r_item["id"])
                    restaurants.append(r_item)
                    new += 1

            print(f"[zomato] page {page}: +{new} restaurants (total {len(restaurants)})")

            if new == 0:
                print("[zomato] No new results, stopping pagination.")
                break

            page += 1

    return restaurants[:max_results]


async def main():
    print("Scraping Zomato...")
    results = await scrape_zomato(keyword="biryani", max_results=20)
    print(f"\nTotal: {len(results)} restaurants")
    if results:
        for r in results[:5]:
            print(f"  {r['name']} | {r['rating']} | {r['delivery_time']} | {r['cuisine']}")
    with open("zomato_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Saved -> zomato_results.json")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
