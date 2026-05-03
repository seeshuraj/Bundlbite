# scraper/swiggy.py
# Swiggy scraper using httpx - direct API calls, no browser needed
# Faster, more reliable, zero asyncio/Playwright issues on Windows

import httpx
import asyncio
from typing import Optional

# Swiggy internal API base
SWIGGY_BASE = "https://www.swiggy.com"
SWIGGY_API  = "https://www.swiggy.com/dapi"

# Headers that mimic a real Chrome browser session
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.swiggy.com/",
    "Origin": "https://www.swiggy.com",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
}


def _parse_restaurant_cards(cards: list) -> list:
    """Extract restaurant info from Swiggy dapi card format."""
    results = []
    for card in cards:
        # Card format varies - try both structures
        info = (
            card.get("card", {}).get("card", {}).get("info")
            or card.get("data")
            or {}
        )
        name = info.get("name")
        if not name:
            continue
        results.append({
            "id": str(info.get("id", "")),
            "name": name,
            "cuisines": info.get("cuisines", []),
            "rating": str(
                info.get("avgRatingString")
                or info.get("avgRating")
                or "0"
            ),
            "delivery_time": info.get("sla", {}).get("deliveryTime", 30),
            "price_for_two": (
                info.get("costForTwo")
                or info.get("costForTwoMessage")
                or "\u20b9300 for two"
            ),
            "image": info.get("cloudinaryImageId", ""),
            "source": "swiggy",
        })
    return results


async def _get_session_cookies(client: httpx.AsyncClient) -> dict:
    """Hit Swiggy homepage to get session cookies."""
    try:
        r = await client.get(SWIGGY_BASE, timeout=15)
        return dict(r.cookies)
    except Exception as e:
        print(f"[Swiggy] Cookie fetch error: {e}")
        return {}


async def fetch_swiggy_restaurants(
    lat: float, lng: float, keyword: str = ""
) -> list:
    """
    Fetch restaurants from Swiggy using direct httpx API calls.
    Uses a persistent async client with session cookies.
    """
    url = (
        f"{SWIGGY_API}/restaurants/list/v5"
        f"?lat={lat}&lng={lng}"
        f"&is-seo-homepage-enabled=true"
        f"&page_type=DESKTOP_WEB_LISTING"
    )

    async with httpx.AsyncClient(
        headers=BASE_HEADERS,
        follow_redirects=True,
        timeout=30,
    ) as client:
        # Step 1: get session cookies from homepage
        cookies = await _get_session_cookies(client)
        print(f"[Swiggy] Got {len(cookies)} session cookies")

        # Step 2: hit the restaurant list API
        try:
            r = await client.get(url, cookies=cookies)
            print(f"[Swiggy] API status: {r.status_code}")

            if r.status_code != 200:
                print(f"[Swiggy] Non-200 response: {r.text[:300]}")
                return []

            data = r.json()

            # Navigate the nested card structure
            all_cards = data.get("data", {}).get("cards", [])
            restaurants = []

            for top_card in all_cards:
                # Cards can be nested several levels deep
                inner = top_card.get("card", {}).get("card", {})
                card_type = inner.get("@type", "")

                # Restaurant grid cards
                if "gridWidget" in card_type or "restaurantListWidget" in card_type:
                    grid_elements = inner.get("gridElements", {}).get("infoWithStyle", {}).get("restaurants", [])
                    restaurants.extend(_parse_restaurant_cards(grid_elements))

                # Direct restaurant cards
                if inner.get("info", {}).get("name"):
                    restaurants.extend(_parse_restaurant_cards([top_card]))

                # Check nested data key
                nested = top_card.get("card", {}).get("card", {}).get("data", {})
                if nested.get("name"):
                    restaurants.extend(_parse_restaurant_cards([{"data": nested}]))

            # Filter by keyword if provided
            if keyword and restaurants:
                kw = keyword.lower()
                filtered = [
                    r for r in restaurants
                    if kw in r["name"].lower()
                    or any(kw in c.lower() for c in r.get("cuisines", []))
                ]
                if filtered:
                    restaurants = filtered

            # Deduplicate by id
            seen = set()
            unique = []
            for r in restaurants:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique.append(r)

            print(f"[Swiggy] Total unique restaurants: {len(unique)}")
            return unique

        except httpx.HTTPError as e:
            print(f"[Swiggy] HTTP error: {e}")
            return []
        except Exception as e:
            print(f"[Swiggy] Unexpected error: {e}")
            import traceback; traceback.print_exc()
            return []


async def fetch_swiggy_menu(
    restaurant_id: str, lat: float, lng: float
) -> list:
    """Fetch menu items for a specific restaurant."""
    url = (
        f"{SWIGGY_API}/menu/pl"
        f"?page-type=REGULAR_MENU&complete-menu=true"
        f"&lat={lat}&lng={lng}"
        f"&restaurantId={restaurant_id}"
        f"&catalog_qa=undefined&submitAction=ENTER"
    )

    async with httpx.AsyncClient(
        headers=BASE_HEADERS,
        follow_redirects=True,
        timeout=30,
    ) as client:
        cookies = await _get_session_cookies(client)
        try:
            r = await client.get(url, cookies=cookies)
            if r.status_code != 200:
                return []

            data = r.json()
            items = []

            for top_card in data.get("data", {}).get("cards", []):
                groups = (
                    top_card.get("groupedCard", {})
                    .get("cardGroupMap", {})
                    .get("REGULAR", {})
                    .get("cards", [])
                )
                for g in groups:
                    for ic in g.get("card", {}).get("card", {}).get("itemCards", []):
                        info = ic.get("card", {}).get("info", {})
                        if info.get("name"):
                            items.append({
                                "id": str(info.get("id", "")),
                                "name": info.get("name", ""),
                                "price": (info.get("price") or 0) / 100,
                                "is_veg": (
                                    info.get("itemAttribute", {})
                                    .get("vegClassifier") == "VEG"
                                ),
                                "description": info.get("description", ""),
                                "image": info.get("imageId", ""),
                            })
            print(f"[Swiggy Menu] {len(items)} items for restaurant {restaurant_id}")
            return items

        except Exception as e:
            print(f"[Swiggy Menu] Error: {e}")
            return []
