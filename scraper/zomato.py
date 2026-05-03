# scraper/zomato.py
# Production Zomato scraper — POST /webroutes/search/home
# Endpoint + payload reverse-engineered via Playwright network capture.
# Integrates with main.py via fetch_zomato_restaurants / fetch_zomato_menu.

import json
import httpx

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Default location blob for Bangalore city-level delivery listing.
# placeId / cellId / deliverySubzoneId are required by Zomato’s backend
# to resolve which delivery zone to use. These values are for the
# Koramangala/UB City DSZ and work for most Bangalore queries.
# For user-specific lat/lng, wire in a /webroutes/search/autoSuggest
# lookup to get the correct placeId for that coordinate.
_BANGALORE_LOC = {
    "latitude":               "12.9716060000000000",
    "longitude":              "77.5943760000000000",
    "userDefinedLatitude":    12.971606,
    "userDefinedLongitude":   77.594376,
    "cityId":                 4,
    "cityName":               "Bengaluru",
    "countryId":              1,
    "countryName":            "India",
    "entityId":               4,
    "entityType":             "city",
    "locationType":           "poi",
    "addressId":              0,
    "isOrderLocation":        1,
    "entityName":             "Table Space UB City, Bengaluru",
    "orderLocationName":      "Table Space UB City, Bengaluru",
    "displayTitle":           "UB City",
    "o2Serviceable":          True,
    "placeId":                "3655",
    "cellId":                 "4300399395616063488",
    "deliverySubzoneId":      3655,
    "placeType":              "DSZ",
    "placeName":              "Table Space UB City, Bengaluru",
    "isO2City":               True,
    "fetchFromGoogle":        False,
    "fetchedFromCookie":      False,
    "isO2OnlyCity":           False,
    "address_template":       [],
    "otherRestaurantsUrl":    "",
}


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


def _make_filters(prev_search: str, postback: str) -> str:
    """Build the JSON-stringified filters string Zomato expects."""
    return json.dumps({
        "searchMetadata": {
            "previousSearchParams": prev_search,
            "postbackParams":       postback,
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
    })


def _parse_restaurant(item: dict) -> dict | None:
    info = item.get("info") or item
    name = info.get("name", "")
    if not name:
        return None

    # Rating
    r = info.get("rating", {})
    rating = str(r.get("aggregate_rating") or r.get("rating", ""))

    # Cuisine
    cuisine = ", ".join(
        c.get("deeplink_text", c.get("name", ""))
        for c in info.get("cuisine", [])
    )

    # Delivery time — Zomato returns this as 'eta' (e.g. "29 mins")
    delivery_time = str(
        info.get("eta")
        or info.get("delivery_time")
        or info.get("deliveryTime")
        or ""
    )

    # Price for two
    price = str(info.get("price", info.get("average_cost_for_two", "")))

    # Image — prefer o2FeaturedImage, fallback to image
    img = info.get("o2FeaturedImage") or info.get("image") or {}
    image_url = img.get("url", img.get("imageUrl", ""))

    # Deep-link URL
    slug = (info.get("actionInfo") or {}).get("clickUrl", "")
    url = f"https://www.zomato.com{slug}" if slug else ""

    return {
        "id":            str(info.get("resId", "")),
        "name":          name,
        "rating":        rating,
        "cuisine":       cuisine,
        "delivery_time": delivery_time,
        "price_for_two": price,
        "image":         image_url,
        "url":           url,
        "source":        "zomato",
    }


async def fetch_zomato_restaurants(
    lat: float,
    lng: float,
    keyword: str = "",
    max_results: int = 40,
) -> list[dict]:
    """
    Fetch restaurant listings from Zomato delivery.
    lat/lng are accepted for API compatibility but Zomato resolves
    location via the DSZ place fields in the payload.
    """
    restaurants: list[dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # Seed cookies + get csrf
        await client.get("https://www.zomato.com", headers=_seed_headers())
        await client.get("https://www.zomato.com/bangalore", headers=_seed_headers())
        cr = await client.get(
            "https://www.zomato.com/webroutes/auth/csrf",
            headers={"User-Agent": BROWSER_UA, "Accept": "application/json",
                     "Referer": "https://www.zomato.com/bangalore/delivery"}
        )
        csrf = cr.json().get("csrf", client.cookies.get("csrf", ""))

        h = _api_headers(csrf)

        # Initial pagination state
        prev_search = json.dumps({
            "PreviousSearchFilter": [
                json.dumps({"category_context": "delivery_home"}),
                "",
            ]
        })
        postback = json.dumps({
            "processed_chain_ids": [],
            "shown_res_count": 0,
        })
        search_id = None

        page = 1
        while len(restaurants) < max_results:
            if search_id:
                pb = json.loads(postback)
                pb["search_id"] = search_id
                postback = json.dumps(pb)

            payload = {
                "context": "delivery",
                "filters": _make_filters(prev_search, postback),
                **_BANGALORE_LOC,
            }

            r = await client.post(
                "https://www.zomato.com/webroutes/search/home",
                headers=h,
                json=payload,
            )

            if r.status_code != 200:
                print(f"[zomato] HTTP {r.status_code} on page {page}")
                break

            try:
                data = r.json()
            except Exception as e:
                print(f"[zomato] parse error: {e}")
                break

            sections = data.get("sections", {})
            sr       = sections.get("SECTION_SEARCH_RESULT", [])
            meta     = sections.get("SECTION_SEARCH_META_INFO", {}).get("searchMetaData", {})

            # Advance pagination cursors
            new_postback = meta.get("postbackParams", "")
            if new_postback:
                postback = new_postback
                try:
                    pb_obj = json.loads(new_postback)
                    search_id = pb_obj.get("search_id", search_id)
                except Exception:
                    pass
            if meta.get("previousSearchParams"):
                prev_search = meta["previousSearchParams"]

            # Parse batch
            new_count = 0
            for item in (sr if isinstance(sr, list) else []):
                parsed = _parse_restaurant(item)
                if parsed and parsed["id"] not in seen_ids:
                    seen_ids.add(parsed["id"])
                    restaurants.append(parsed)
                    new_count += 1

            has_more = meta.get("hasMore", False)
            if new_count == 0 or not has_more:
                break

            page += 1

    return restaurants[:max_results]


async def fetch_zomato_menu(restaurant_id: str) -> list[dict]:
    """
    Fetch menu items for a Zomato restaurant.
    Uses the restaurant's order page via getPage webroute.
    Returns list of {name, price, description, image, category}.
    """
    # TODO: implement menu scraping via getPage for individual restaurant
    # For now returns empty list — restaurant listing is the MVP requirement
    return []
