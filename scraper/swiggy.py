# scraper/swiggy.py
# Swiggy scraper with anti-bot bypass

import json
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

SWIGGY_API_BASE = "https://www.swiggy.com/dapi"


def _stealth_args():
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--window-size=1366,768",
        "--disable-gpu",
        "--lang=en-IN",
    ]


async def _apply_stealth(page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-IN','en-US','en','hi'] });
        window.chrome = { runtime: {} };
    """)


def _parse_restaurant_cards(cards: list) -> list:
    """Parse Swiggy API restaurant cards into clean dicts."""
    results = []
    for r in cards:
        # Swiggy nests data differently across API versions
        info = (
            r.get("card", {}).get("card", {}).get("info") or
            r.get("data", {}) or
            {}
        )
        name = info.get("name") or info.get("restaurant", {}).get("info", {}).get("name")
        if not name:
            continue
        results.append({
            "id": info.get("id", ""),
            "name": name,
            "cuisines": info.get("cuisines", []),
            "rating": str(info.get("avgRatingString") or info.get("avgRating") or "0"),
            "delivery_time": info.get("sla", {}).get("deliveryTime", 30),
            "price_for_two": info.get("costForTwo") or info.get("costForTwoMessage") or "₹300 for two",
            "image": info.get("cloudinaryImageId", ""),
            "source": "swiggy",
        })
    return results


async def fetch_swiggy_restaurants(lat: float, lng: float, keyword: str = "") -> list:
    """
    Fetch restaurants from Swiggy.
    Strategy 1: Intercept /dapi network calls (fast)
    Strategy 2: In-page fetch with session cookies (fallback)
    Strategy 3: Direct API call without browser (fastest, may need cookies)
    """
    intercepted_data = []
    api_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=_stealth_args(),
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        page = await context.new_page()
        await _apply_stealth(page)

        # --- Strategy 1: Intercept dapi network calls ---
        async def handle_route(route, request):
            url = request.url
            if "/dapi/restaurants" in url:
                try:
                    response = await route.fetch()
                    try:
                        body = await response.json()
                        cards = (
                            body.get("data", {}).get("cards") or
                            body.get("data", {}).get("restaurants") or []
                        )
                        parsed = _parse_restaurant_cards(cards)
                        if parsed:
                            intercepted_data.extend(parsed)
                            api_event.set()
                    except Exception as parse_err:
                        print(f"[Swiggy] Parse error: {parse_err}")
                    await route.fulfill(response=response)
                except Exception as fetch_err:
                    print(f"[Swiggy] Route fetch error: {fetch_err}")
                    await route.continue_()
            else:
                await route.continue_()

        await page.route("**/*", handle_route)

        swiggy_url = "https://www.swiggy.com/"
        try:
            await page.goto(swiggy_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await asyncio.wait_for(api_event.wait(), timeout=12)
            except asyncio.TimeoutError:
                print("[Swiggy] API interception timed out, trying fallback...")
        except Exception as nav_err:
            print(f"[Swiggy] Navigation error: {nav_err}")

        # --- Strategy 2: In-page fetch using session cookies ---
        if not intercepted_data:
            try:
                cookies = await context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                api_url = (
                    f"https://www.swiggy.com/dapi/restaurants/list/v5"
                    f"?lat={lat}&lng={lng}&is-seo-homepage-enabled=true"
                    f"&page_type=DESKTOP_WEB_LISTING"
                )
                result = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch('{api_url}', {{
                                credentials: 'include',
                                headers: {{ 'Content-Type': 'application/json' }}
                            }});
                            return await r.json();
                        }} catch(e) {{ return {{ error: e.toString() }}; }}
                    }}
                """)
                if result and not result.get("error"):
                    cards = result.get("data", {}).get("cards", [])
                    intercepted_data.extend(_parse_restaurant_cards(cards))
                    print(f"[Swiggy] Fallback fetch got {len(intercepted_data)} restaurants")
                else:
                    print(f"[Swiggy] Fallback fetch error: {result.get('error')}")
            except Exception as fb_err:
                print(f"[Swiggy] Fallback error: {fb_err}")

        await browser.close()

    print(f"[Swiggy] Total restaurants found: {len(intercepted_data)}")
    return intercepted_data


async def fetch_swiggy_menu(restaurant_id: str, lat: float, lng: float) -> list:
    items = []
    menu_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=_stealth_args())
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
        )
        page = await context.new_page()
        await _apply_stealth(page)

        async def handle_menu_route(route, request):
            if "/dapi/menu" in request.url:
                try:
                    response = await route.fetch()
                    try:
                        body = await response.json()
                        cards = body.get("data", {}).get("cards", [])
                        for card in cards:
                            groups = (
                                card.get("groupedCard", {})
                                .get("cardGroupMap", {})
                                .get("REGULAR", {})
                                .get("cards", [])
                            )
                            for g in groups:
                                item_cards = g.get("card", {}).get("card", {}).get("itemCards", [])
                                for ic in item_cards:
                                    info = ic.get("card", {}).get("info", {})
                                    if info.get("name"):
                                        items.append({
                                            "id": info.get("id", ""),
                                            "name": info.get("name", ""),
                                            "price": (info.get("price") or 0) / 100,
                                            "is_veg": info.get("itemAttribute", {}).get("vegClassifier") == "VEG",
                                            "rating": str(info.get("ratings", {}).get("aggregatedRating", {}).get("rating", "0")),
                                            "description": info.get("description", ""),
                                        })
                        menu_event.set()
                    except Exception:
                        pass
                    await route.fulfill(response=response)
                except Exception:
                    await route.continue_()
            else:
                await route.continue_()

        await page.route("**/*", handle_menu_route)
        url = f"https://www.swiggy.com/restaurants/r-{restaurant_id}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.wait_for(menu_event.wait(), timeout=12)
        except Exception:
            pass

        await browser.close()

    return items
