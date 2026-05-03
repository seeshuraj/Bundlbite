# scraper/zomato_scraper.py
# Production Zomato scraper — uses POST /webroutes/search/home
# Payload reverse-engineered via Playwright network capture.
#
# Usage: .\venv\Scripts\python.exe scraper\zomato_scraper.py

import asyncio
import json
import sys
import httpx

# ---------------------------------------------------------------------------
# Default location: Koramangala, Bangalore
# To scrape a different area, pass lat/lng + update the place fields, or
# use Zomato’s /webroutes/search/autoSuggest to resolve an address to IDs.
# ---------------------------------------------------------------------------
DEFAULT_LOC = {
    "latitude":           "12.9352000000000000",
    "longitude":          "77.6245000000000000",
    "userDefinedLatitude":  12.9352,
    "userDefinedLongitude": 77.6245,
    "cityId":             4,
    "cityName":           "Bengaluru",
    "countryId":          1,
    "countryName":        "India",
    "entityId":           4,
    "entityType":         "city",
    "locationType":       "poi",
    "addressId":          0,
    "isOrderLocation":    1,
    "entityName":         "Koramangala, Bengaluru",
    "orderLocationName":  "Koramangala, Bengaluru",
    "displayTitle":       "Koramangala",
    "o2Serviceable":      True,
    "placeId":            "3655",
    "cellId":             "4300399395616063488",
    "deliverySubzoneId":  3655,
    "placeType":          "DSZ",
    "placeName":          "Koramangala, Bengaluru",
    "isO2City":           True,
    "fetchFromGoogle":    False,
    "fetchedFromCookie":  False,
    "isO2OnlyCity":       False,
    "address_template":   [],
    "otherRestaurantsUrl": "",
}

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _seed_headers() -> dict:
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
    }


def _api_headers(csrf: str) -> dict:
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN",
        "Content-Type": "application/json",
        "Referer": "https://www.zomato.com/bangalore/delivery",
        "Origin": "https://www.zomato.com",
        "x-zomato-csrft": csrf,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def _make_filters(previous_search_params: str, postback_params: str) -> str:
    """Build the JSON-stringified filters string Zomato expects."""
    filters_obj = {
        "searchMetadata": {
            "previousSearchParams": previous_search_params,
            "postbackParams":       postback_params,
            "totalResults":         1374,
            "hasMore":              True,
            "getInactive":          False,
        },
        "dineoutAdsMetaData": {},
        "appliedFilter": [
            {
                "filterType":  "category_sheet",
                "filterValue": "delivery_home",
                "isHidden":    True,
                "isApplied":   True,
                "postKey":     json.dumps({"category_context": "delivery_home"}),
            }
        ],
        "urlParamsForAds": {},
    }
    return json.dumps(filters_obj)


def _initial_postback() -> str:
    return json.dumps({
        "PreviousSearchFilter": [
            json.dumps({"category_context": "delivery_home"}),
            "",
        ]
    })


def parse_restaurant(item: dict) -> dict | None:
    info = item.get("info") or item
    if not info.get("name"):
        return None

    rating_obj = info.get("rating", {})
    rating = str(
        rating_obj.get("aggregate_rating")
        or rating_obj.get("rating", "")
    )

    cuisine = ", ".join(
        c.get("deeplink_text", c.get("name", ""))
        for c in info.get("cuisine", [])
    )

    delivery_time = str(
        info.get("delivery_time")
        or info.get("deliveryTime")
        or info.get("eta", "")
    )

    price = str(info.get("price", info.get("average_cost_for_two", "")))

    image_obj = info.get("image", {}) or info.get("o2FeaturedImage", {})
    image_url = image_obj.get("url", image_obj.get("imageUrl", ""))

    action = info.get("actionInfo", {})
    slug = action.get("clickUrl", "")
    url = f"https://www.zomato.com{slug}" if slug else ""

    return {
        "id":            str(info.get("resId", "")),
        "name":          info.get("name", ""),
        "rating":        rating,
        "cuisine":       cuisine,
        "delivery_time": delivery_time,
        "price_for_two": price,
        "image":         image_url,
        "url":           url,
        "source":        "zomato",
    }


async def scrape_zomato(
    keyword: str = "",
    location: dict = None,
    max_results: int = 40,
) -> list[dict]:
    loc = location or DEFAULT_LOC
    restaurants: list[dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # Seed cookies
        await client.get("https://www.zomato.com", headers=_seed_headers())
        await client.get("https://www.zomato.com/bangalore", headers=_seed_headers())

        # Get fresh csrf
        cr = await client.get(
            "https://www.zomato.com/webroutes/auth/csrf",
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/json",
                "Referer": "https://www.zomato.com/bangalore/delivery",
            }
        )
        csrf = cr.json().get("csrf", client.cookies.get("csrf", ""))
        print(f"[zomato] csrf: {csrf[:16]}...")

        h = _api_headers(csrf)

        # Pagination state
        previous_search_params = json.dumps({
            "PreviousSearchFilter": [
                json.dumps({"category_context": "delivery_home"}),
                "",
            ]
        })
        postback_params = json.dumps({
            "processed_chain_ids": [],
            "shown_res_count": 0,
        })
        search_id = None

        page = 1
        while len(restaurants) < max_results:
            if search_id:
                pb = json.loads(postback_params)
                pb["search_id"] = search_id
                postback_params = json.dumps(pb)

            payload = {
                "context": "delivery",
                "filters": _make_filters(previous_search_params, postback_params),
                **loc,
            }

            r = await client.post(
                "https://www.zomato.com/webroutes/search/home",
                headers=h,
                json=payload,
            )

            if r.status_code != 200:
                print(f"[zomato] page {page} -> HTTP {r.status_code}")
                print(f"  response: {r.text[:300]}")
                break

            try:
                data = r.json()
            except Exception as e:
                print(f"[zomato] parse error: {e}")
                break

            sections = data.get("sections", {})
            sr = sections.get("SECTION_SEARCH_RESULT", [])
            meta = sections.get("SECTION_SEARCH_META_INFO", {}).get("searchMetaData", {})

            # Update pagination state from response
            new_postback = meta.get("postbackParams", "")
            if new_postback:
                postback_params = new_postback
                try:
                    pb_obj = json.loads(new_postback)
                    search_id = pb_obj.get("search_id", search_id)
                except Exception:
                    pass

            new_previous = meta.get("previousSearchParams", "")
            if new_previous:
                previous_search_params = new_previous

            # Parse restaurants
            batch = []
            for item in sr if isinstance(sr, list) else []:
                if isinstance(item, dict):
                    parsed = parse_restaurant(item)
                    if parsed:
                        batch.append(parsed)

            new_count = 0
            for item in batch:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    restaurants.append(item)
                    new_count += 1

            has_more = meta.get("hasMore", False)
            print(f"[zomato] page {page}: +{new_count} restaurants "
                  f"(total {len(restaurants)}) hasMore={has_more}")

            if new_count == 0 or not has_more:
                print("[zomato] Done paginating.")
                break

            page += 1

    return restaurants[:max_results]


async def main():
    print("Scraping Zomato...")
    results = await scrape_zomato(keyword="", max_results=30)
    print(f"\nTotal: {len(results)} restaurants")
    for r in results[:5]:
        print(f"  {r['name']} | {r['rating']} stars | {r['delivery_time']} | {r['cuisine']}")
    with open("zomato_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Saved -> zomato_results.json")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
