# scraper/swiggy.py
# Swiggy scraper using httpx - direct API, no Playwright needed

import httpx
from typing import Optional

SWIGGY_API = "https://www.swiggy.com/dapi"

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


def _parse_restaurant(info: dict) -> Optional[dict]:
    """Parse a single restaurant info dict into our schema."""
    name = info.get("name")
    if not name:
        return None
    return {
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
    }


def _extract_from_cards(cards: list) -> list:
    """
    Real Swiggy card structure (confirmed from API):
    cards[].card.card.gridElements.infoWithStyle.restaurants[].info
    """
    results = []
    for card in cards:
        inner = card.get("card", {}).get("card", {})
        grid = inner.get("gridElements", {}).get("infoWithStyle", {})
        restaurants = grid.get("restaurants", [])
        for r in restaurants:
            parsed = _parse_restaurant(r.get("info", {}))
            if parsed:
                results.append(parsed)
    return results


async def fetch_swiggy_restaurants(
    lat: float, lng: float, keyword: str = ""
) -> list:
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
        # Warm up session
        try:
            await client.get("https://www.swiggy.com", timeout=10)
        except Exception:
            pass

        r = await client.get(url)
        print(f"[Swiggy] Status: {r.status_code}")

        if r.status_code != 200:
            print(f"[Swiggy] Error body: {r.text[:200]}")
            return []

        data = r.json()
        if data.get("statusCode", -1) != 0:
            print(f"[Swiggy] API statusCode: {data.get('statusCode')}")
            return []

        cards = data.get("data", {}).get("cards", [])
        restaurants = _extract_from_cards(cards)
        print(f"[Swiggy] Extracted {len(restaurants)} restaurants")

        # Keyword filter
        if keyword and restaurants:
            kw = keyword.lower()
            filtered = [
                r for r in restaurants
                if kw in r["name"].lower()
                or any(kw in c.lower() for c in r.get("cuisines", []))
            ]
            restaurants = filtered if filtered else restaurants
            print(f"[Swiggy] After keyword filter '{keyword}': {len(restaurants)}")

        # Deduplicate
        seen, unique = set(), []
        for r in restaurants:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        print(f"[Swiggy] Final: {len(unique)} unique restaurants")
        return unique


async def fetch_swiggy_menu(
    restaurant_id: str, lat: float, lng: float
) -> list:
    url = (
        f"{SWIGGY_API}/menu/pl"
        f"?page-type=REGULAR_MENU&complete-menu=true"
        f"&lat={lat}&lng={lng}"
        f"&restaurantId={restaurant_id}"
        f"&catalog_qa=undefined&submitAction=ENTER"
    )

    async with httpx.AsyncClient(
        headers=BASE_HEADERS, follow_redirects=True, timeout=30
    ) as client:
        try:
            await client.get("https://www.swiggy.com", timeout=10)
        except Exception:
            pass

        r = await client.get(url)
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
                for ic in (
                    g.get("card", {}).get("card", {}).get("itemCards", [])
                ):
                    info = ic.get("card", {}).get("info", {})
                    if info.get("name"):
                        items.append({
                            "id": str(info.get("id", "")),
                            "name": info["name"],
                            "price": (info.get("price") or 0) / 100,
                            "is_veg": (
                                info.get("itemAttribute", {})
                                .get("vegClassifier") == "VEG"
                            ),
                            "description": info.get("description", ""),
                            "image": info.get("imageId", ""),
                        })

        print(f"[Swiggy Menu] {len(items)} items")
        return items
