# scraper/zomato.py
# Production Zomato scraper — POST /webroutes/search/home
# Endpoint + payload reverse-engineered via Playwright network capture.
# Integrates with main.py via fetch_zomato_restaurants / fetch_zomato_menu.

import json
import re
import httpx

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Default location blob for Bangalore city-level delivery listing.
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


def _extract_delivery_time(info: dict) -> str:
    """
    Probe all known Zomato shapes for delivery ETA.
    NOTE: webroutes/search/home does NOT return ETA in listing responses.
    ETA is only available on the individual restaurant page.
    Returns empty string if not present — handled gracefully by the frontend.
    """
    # etaRange dict: {"minTime": 25, "maxTime": 40}
    eta_raw = info.get("etaRange")
    if isinstance(eta_raw, dict):
        t = eta_raw.get("minTime") or eta_raw.get("maxTime")
        if t is not None:
            return str(t)

    # plain int/str
    for field in ("eta", "deliveryTime", "delivery_time", "eta_text"):
        val = info.get(field)
        if val is not None and str(val).strip():
            return str(val)

    # nested under orderDeliveryInfo / deliveryInfo / deliveryMeta / delivery
    for key in ("orderDeliveryInfo", "deliveryInfo", "deliveryMeta", "delivery"):
        sub = info.get(key)
        if not isinstance(sub, dict):
            continue
        eta_range = sub.get("etaRange")
        if isinstance(eta_range, dict):
            t = eta_range.get("minTime") or eta_range.get("maxTime")
            if t is not None:
                return str(t)
        for field in ("eta", "deliveryTime", "delivery_time"):
            val = sub.get(field)
            if val is not None and str(val).strip():
                return str(val)

    return ""


def _extract_price(info: dict) -> str:
    """
    Probe all known Zomato shapes for price.

    Confirmed live shape (webroutes/search/home listing response):
      info.costText = {"text": "\u20b9200 for one"}

    Also handles older shapes:
      info.cft / info.cfo = {"text": "\u20b9400 for two"}
      info.price / info.average_cost_for_two / info.costForTwo = 400 (int)
    """
    # 1. costText.text — CONFIRMED live key e.g. "\u20b9200 for one"
    cost_text = info.get("costText")
    if isinstance(cost_text, dict):
        text = cost_text.get("text", "")
        if text:
            # Normalise "X for one" -> "X for two" by doubling the amount
            m = re.search(r"[\u20b9Rs\.]*\s*(\d+)\s*for\s*one", text, re.IGNORECASE)
            if m:
                return f"\u20b9{int(m.group(1)) * 2} for two"
            # Already "for two" or other format — return as-is
            return text

    # 2. cft (cost for two) or cfo (cost for one) objects
    for key in ("cft", "cfo"):
        obj = info.get(key)
        if isinstance(obj, dict):
            text = obj.get("text", "")
            if text:
                if key == "cfo":
                    m = re.search(r"(\d+)", text)
                    if m:
                        return f"\u20b9{int(m.group(1)) * 2} for two"
                return text

    # 3. Plain numeric fields
    for field in ("price", "average_cost_for_two", "costForTwo", "cost_for_two"):
        val = info.get(field)
        if val is not None and str(val).strip() not in ("", "0", "None"):
            try:
                return f"\u20b9{int(val)} for two"
            except (ValueError, TypeError):
                return str(val)

    # 4. priceRange string or int
    pr = info.get("priceRange")
    if pr is not None and str(pr).strip() not in ("", "0", "None"):
        try:
            return f"\u20b9{int(pr)} for two"
        except (ValueError, TypeError):
            return str(pr)

    # 5. Nested under orderDeliveryInfo / deliveryInfo
    for key in ("orderDeliveryInfo", "deliveryInfo"):
        sub = info.get(key)
        if not isinstance(sub, dict):
            continue
        for field in ("costForTwo", "price", "average_cost_for_two"):
            val = sub.get(field)
            if val is not None and str(val).strip() not in ("", "0"):
                try:
                    return f"\u20b9{int(val)} for two"
                except (ValueError, TypeError):
                    return str(val)

    return ""


def _parse_restaurant(item: dict) -> dict | None:
    # Zomato wraps the real data under 'info' in SECTION_SEARCH_RESULT
    info = item.get("info") or item
    name = info.get("name", "")
    if not name:
        return None

    # ── Rating ──────────────────────────────────────────────────────
    r = info.get("rating", {})
    if isinstance(r, dict):
        rating = str(r.get("aggregate_rating") or r.get("rating", ""))
    else:
        rating = str(r)

    # ── Cuisine ─────────────────────────────────────────────────────
    cuisine_raw = info.get("cuisine", [])
    if isinstance(cuisine_raw, list):
        cuisine = ", ".join(
            c.get("deeplink_text", c.get("name", ""))
            for c in cuisine_raw
            if isinstance(c, dict)
        )
    else:
        cuisine = str(cuisine_raw)

    # ── Delivery time & Price ───────────────────────────────────
    delivery_time = _extract_delivery_time(info)
    price_for_two = _extract_price(info)

    # ── Image ───────────────────────────────────────────────────────
    img = info.get("featuredImage") or info.get("o2FeaturedImage") or info.get("image") or {}
    if isinstance(img, dict):
        image_url = img.get("url", img.get("imageUrl", ""))
    else:
        image_url = str(img)

    # ── Deep-link URL ───────────────────────────────────────────────
    action = info.get("actionInfo") or info.get("action") or {}
    slug = action.get("clickUrl") or action.get("deeplink") or ""
    if slug and slug.startswith("/"):
        url = f"https://www.zomato.com{slug}"
    elif slug and slug.startswith("http"):
        url = slug
    else:
        url = ""

    return {
        "id":            str(info.get("resId", info.get("id", ""))),
        "name":          name,
        "rating":        rating,
        "cuisine":       cuisine,
        "delivery_time": delivery_time,
        "price_for_two": price_for_two,
        "image":         image_url,
        "url":           url,
        "source":        "zomato",
    }


def _is_relevant(restaurant: dict, keyword: str) -> bool:
    """Return True if the restaurant matches the keyword in name or cuisine."""
    if not keyword:
        return True
    kw = keyword.lower()
    name = restaurant.get("name", "").lower()
    cuisine = restaurant.get("cuisine", "").lower()
    return kw in name or kw in cuisine


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
    When a keyword is supplied, results are filtered to matching
    names/cuisines so the /compare endpoint returns relevant data.
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
 hitting_limit = False
        while len(restaurants) < max_results and not hitting_limit:
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

            for item in (sr if isinstance(sr, list) else []):
                parsed = _parse_restaurant(item)
                if parsed and parsed["id"] not in seen_ids:
                    seen_ids.add(parsed["id"])
                    if _is_relevant(parsed, keyword):
                        restaurants.append(parsed)

            has_more = meta.get("hasMore", False)
            if not has_more or page >= 8:
                hitting_limit = True

            page += 1

    print(f"[zomato] Final: {len(restaurants)} restaurants (keyword='{keyword}')")
    return restaurants[:max_results]


async def fetch_zomato_menu(restaurant_id: str) -> list[dict]:
    """
    Fetch menu items for a Zomato restaurant.
    Returns list of {name, price, description, image, category}.
    """
    # TODO: implement menu scraping via getPage for individual restaurant
    return []
