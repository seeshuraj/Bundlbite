# scraper/zomato.py
# Zomato scraper using httpx - direct API calls, no Playwright needed
# Mirrors the same pattern as swiggy.py

import httpx
from typing import Optional

ZOMATOBASE = "https://www.zomato.com"
ZOMATOAPI  = "https://www.zomato.com/webroutes"

# Zomato expects a mobile-ish Chrome UA for best API compatibility
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.zomato.com/",
    "Origin": "https://www.zomato.com",
    "x-zomato-csrft": "",  # will be filled after session
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Connection": "keep-alive",
}


def _parse_restaurant(r: dict) -> Optional[dict]:
    """Normalise a Zomato restaurant object into our schema."""
    # Zomato nests info differently depending on endpoint
    info = r.get("info") or r.get("restaurant") or r
    rid  = info.get("id") or info.get("resId")
    name = info.get("name") or info.get("resName")
    if not name or not rid:
        return None

    # Cuisines come as a comma-separated string or a list
    raw_cuisines = info.get("cuisine") or info.get("cuisines") or ""
    if isinstance(raw_cuisines, str):
        cuisines = [c.strip() for c in raw_cuisines.split(",") if c.strip()]
    else:
        cuisines = raw_cuisines

    rating = (
        info.get("rating", {}).get("aggregate_rating")
        or info.get("avgRating")
        or info.get("ratingObj", {}).get("title", {}).get("text")
        or "0"
    )

    delivery_time = (
        info.get("deliveryTime")
        or info.get("etd")
        or info.get("delivery_stats", {}).get("delivery_time")
        or 35
    )
    if isinstance(delivery_time, str):
        delivery_time = int("".join(filter(str.isdigit, delivery_time)) or 35)

    return {
        "id": str(rid),
        "name": name,
        "cuisines": cuisines,
        "rating": str(rating),
        "delivery_time": delivery_time,
        "price_for_two": str(
            info.get("cost_for_two")
            or info.get("costForTwo")
            or "\u20b9400 for two"
        ),
        "image": info.get("featured_image") or info.get("thumb") or "",
        "source": "zomato",
    }


async def _get_session(client: httpx.AsyncClient) -> str:
    """Hit Zomato homepage to get CSRF token + cookies."""
    try:
        r = await client.get(ZOMATOBASE, timeout=15)
        # CSRF token is in cookie 'csrft'
        csrf = r.cookies.get("csrft", "")
        print(f"[Zomato] Session CSRF: {'ok' if csrf else 'missing'}")
        return csrf
    except Exception as e:
        print(f"[Zomato] Session error: {e}")
        return ""


async def fetch_zomato_restaurants(
    lat: float, lng: float, keyword: str = ""
) -> list:
    """
    Fetch restaurants via Zomato's internal webroutes search API.
    Falls back to the delivery listing endpoint if search returns nothing.
    """
    async with httpx.AsyncClient(
        headers=BASE_HEADERS,
        follow_redirects=True,
        timeout=30,
    ) as client:
        csrf = await _get_session(client)
        if csrf:
            client.headers.update({"x-zomato-csrft": csrf})

        restaurants = []

        # --- Strategy 1: webroutes search API ---
        search_term = keyword or "biryani"
        search_url = (
            f"{ZOMATOAPI}/search"
            f"?q={search_term}"
            f"&lat={lat}&lng={lng}"
            f"&deeplink_filters=WyvNBywwLDYwXQ%3D%3D"
            f"&fetch_sub_zones=1"
        )
        try:
            r = await client.get(search_url)
            print(f"[Zomato] Search API status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                # Results can be in sections[].restaurant_count / sections[].cards
                sections = data.get("sections", [])
                for section in sections:
                    cards = section.get("cards", []) or section.get("restaurants", [])
                    for card in cards:
                        parsed = _parse_restaurant(card)
                        if parsed:
                            restaurants.append(parsed)
        except Exception as e:
            print(f"[Zomato] Search error: {e}")

        # --- Strategy 2: delivery listing page scrape ---
        if not restaurants:
            try:
                listing_url = (
                    f"{ZOMATOAPI}/getDeliveryRestaurants"
                    f"?lat={lat}&lng={lng}&filters={{\"filter\":[]}}"
                )
                r2 = await client.get(listing_url)
                print(f"[Zomato] Listing API status: {r2.status_code}")
                if r2.status_code == 200:
                    data2 = r2.json()
                    for section in data2.get("sections", []):
                        for card in section.get("cards", []):
                            parsed = _parse_restaurant(card)
                            if parsed:
                                restaurants.append(parsed)
            except Exception as e:
                print(f"[Zomato] Listing fallback error: {e}")

        # --- Strategy 3: ordering API ---
        if not restaurants:
            try:
                order_url = (
                    f"https://api.zomato.com/api/v2.1/search"
                    f"?entity_type=zone&lat={lat}&lon={lng}"
                    f"&q={search_term}&sort=rating&order=desc"
                )
                r3 = await client.get(order_url, headers={
                    **BASE_HEADERS,
                    "Accept": "application/json",
                })
                print(f"[Zomato] Public API status: {r3.status_code}")
                if r3.status_code == 200:
                    data3 = r3.json()
                    for r_wrap in data3.get("restaurants", []):
                        parsed = _parse_restaurant(r_wrap)
                        if parsed:
                            restaurants.append(parsed)
            except Exception as e:
                print(f"[Zomato] Public API error: {e}")

        print(f"[Zomato] Raw restaurants: {len(restaurants)}")

        # Keyword filter
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
        seen, unique = set(), []
        for r in restaurants:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        print(f"[Zomato] Final: {len(unique)} unique restaurants")
        return unique


async def fetch_zomato_menu(restaurant_id: str) -> list:
    """Fetch menu from Zomato's internal menu webroute."""
    url = f"{ZOMATOAPI}/order/getPage?resId={restaurant_id}&type=menu"

    async with httpx.AsyncClient(
        headers=BASE_HEADERS,
        follow_redirects=True,
        timeout=30,
    ) as client:
        csrf = await _get_session(client)
        if csrf:
            client.headers.update({"x-zomato-csrft": csrf})

        items = []
        try:
            r = await client.get(url)
            if r.status_code != 200:
                return []

            data = r.json()
            # Navigate Zomato menu structure
            menus = (
                data.get("sections", {})
                .get("SECTION_BASIC_INFO", {})
                .get("menus", [])
            )
            for menu in menus:
                for category in menu.get("menu", {}).get("categories", []):
                    cat_name = category.get("category", {}).get("name", "")
                    for item_wrap in category.get("category", {}).get("items", []):
                        item = item_wrap.get("item", {})
                        if item.get("name"):
                            items.append({
                                "id": str(item.get("id", "")),
                                "name": item["name"],
                                "price": float(item.get("price", 0)),
                                "is_veg": item.get("item_tag") == "veg",
                                "description": item.get("desc", ""),
                                "category": cat_name,
                                "rating": str(item.get("item_rating", {}).get("rating_text", "")),
                            })
        except Exception as e:
            print(f"[Zomato Menu] Error: {e}")

        print(f"[Zomato Menu] {len(items)} items for {restaurant_id}")
        return items
