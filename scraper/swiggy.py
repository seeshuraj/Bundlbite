# scraper/swiggy.py
# Swiggy scraper using httpx - direct API, no Playwright needed
# v2: adds search/v3 endpoint for keyword queries (returns more relevant results)

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

    # Cuisines can be a list or a comma-separated string depending on endpoint
    raw_cuisines = info.get("cuisines", [])
    if isinstance(raw_cuisines, str):
        cuisines = [c.strip() for c in raw_cuisines.split(",")]
    else:
        cuisines = raw_cuisines

    return {
        "id": str(info.get("id", "")),
        "name": name,
        "cuisines": cuisines,
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


def _extract_from_search_cards(cards: list) -> list:
    """
    Swiggy search/v3 response structure:
    cards[].groupedCard.cardGroupMap.RESTAURANT.cards[].card.card
      -> {"@type": "...", "info": {...}}
    Also handles flat card.card.info structure.
    """
    results = []
    for card in cards:
        # Path 1: groupedCard (search endpoint)
        grouped = card.get("groupedCard", {})
        for group_key, group_val in grouped.get("cardGroupMap", {}).items():
            for inner_card in group_val.get("cards", []):
                info = (
                    inner_card.get("card", {}).get("card", {}).get("info")
                    or inner_card.get("card", {}).get("info")
                )
                if info and info.get("name"):
                    parsed = _parse_restaurant(info)
                    if parsed:
                        results.append(parsed)
        # Path 2: direct card.card.info (listing endpoint)
        direct_info = card.get("card", {}).get("card", {}).get("info")
        if direct_info and direct_info.get("name"):
            parsed = _parse_restaurant(direct_info)
            if parsed:
                results.append(parsed)
    return results


def _dedup(restaurants: list) -> list:
    seen, unique = set(), []
    for r in restaurants:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique


async def _fetch_swiggy_search(client: httpx.AsyncClient, lat: float, lng: float, keyword: str) -> list:
    """
    Use Swiggy's search/v3 endpoint for keyword-based restaurant queries.
    Returns more relevant results than the listing endpoint for specific cuisines.
    """
    url = (
        f"{SWIGGY_API}/restaurants/search/v3"
        f"?lat={lat}&lng={lng}"
        f"&str={keyword}"
        f"&trackingId=undefined"
        f"&submitAction=ENTER"
        f"&queryUniqueId="
        f"&selectedPLTab=RESTAURANT"
    )
    try:
        r = await client.get(url, timeout=20)
        print(f"[Swiggy Search] Status: {r.status_code} for keyword='{keyword}'")
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("statusCode", -1) != 0:
            print(f"[Swiggy Search] API statusCode: {data.get('statusCode')}")
            return []
        cards = data.get("data", {}).get("cards", [])
        results = _extract_from_search_cards(cards)
        # Also try the top-level restaurants list some API versions return
        for card in cards:
            restaurants_list = (
                card.get("card", {}).get("card", {})
                    .get("gridElements", {}).get("infoWithStyle", {})
                    .get("restaurants", [])
            )
            for rr in restaurants_list:
                parsed = _parse_restaurant(rr.get("info", {}))
                if parsed:
                    results.append(parsed)
        results = _dedup(results)
        print(f"[Swiggy Search] Extracted {len(results)} restaurants")
        return results
    except Exception as e:
        print(f"[Swiggy Search] Exception: {e}")
        return []


async def fetch_swiggy_restaurants(
    lat: float, lng: float, keyword: str = ""
) -> list:
    async with httpx.AsyncClient(
        headers=BASE_HEADERS,
        follow_redirects=True,
        timeout=30,
    ) as client:
        # Warm up session cookie
        try:
            await client.get("https://www.swiggy.com", timeout=10)
        except Exception:
            pass

        results = []

        # ── Strategy 1: search/v3 when keyword is provided ──────────────
        if keyword:
            results = await _fetch_swiggy_search(client, lat, lng, keyword)

        # ── Strategy 2: listing endpoint (always runs as fallback/supplement) ──
        list_url = (
            f"{SWIGGY_API}/restaurants/list/v5"
            f"?lat={lat}&lng={lng}"
            f"&is-seo-homepage-enabled=true"
            f"&page_type=DESKTOP_WEB_LISTING"
        )
        try:
            r = await client.get(list_url)
            print(f"[Swiggy List] Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if data.get("statusCode", -1) == 0:
                    cards = data.get("data", {}).get("cards", [])
                    list_results = _extract_from_cards(cards)
                    print(f"[Swiggy List] Extracted {len(list_results)} restaurants")
                    # Merge: add list results not already in search results
                    results = results + list_results
        except Exception as e:
            print(f"[Swiggy List] Exception: {e}")

        # ── Deduplicate merged set ───────────────────────────────────────
        results = _dedup(results)

        # ── Keyword filter on merged set ────────────────────────────────
        if keyword and results:
            kw = keyword.lower()
            filtered = [
                r for r in results
                if kw in r["name"].lower()
                or any(kw in c.lower() for c in r.get("cuisines", []))
            ]
            # Only apply filter if it returns results; otherwise keep all
            if filtered:
                results = filtered
            print(f"[Swiggy] After keyword filter '{keyword}': {len(results)}")

        print(f"[Swiggy] Final: {len(results)} unique restaurants")
        return results


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
