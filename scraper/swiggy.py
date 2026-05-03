# scraper/swiggy.py
# Swiggy scraper - uses SYNC Playwright in a ThreadPoolExecutor
# This permanently bypasses the Windows asyncio ProactorEventLoop issue.
# Playwright runs in its own thread with its own event loop.

import json
import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

# Shared thread pool for Playwright (max 2 concurrent browsers)
_executor = ThreadPoolExecutor(max_workers=2)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def _stealth_args():
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--window-size=1366,768",
        "--disable-gpu",
        "--lang=en-IN",
    ]


def _apply_stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-IN','en-US','en','hi'] });
        window.chrome = { runtime: {} };
    """)


def _parse_cards(cards: list) -> list:
    results = []
    for r in cards:
        info = (
            r.get("card", {}).get("card", {}).get("info") or
            r.get("data") or {}
        )
        name = info.get("name")
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


# -------------------------------------------------------
# SYNC Playwright function — runs in a thread
# -------------------------------------------------------
def _sync_fetch_restaurants(lat: float, lng: float, keyword: str) -> list:
    """Sync Playwright scrape. Called from a thread pool."""
    intercepted = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=_stealth_args(),
        )
        context = browser.new_context(
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
        page = context.new_page()
        _apply_stealth(page)

        # Intercept Swiggy dapi calls
        def handle_route(route):
            url = route.request.url
            if "/dapi/restaurants" in url:
                try:
                    response = route.fetch()
                    try:
                        body = response.json()
                        cards = (
                            body.get("data", {}).get("cards") or
                            body.get("data", {}).get("restaurants") or []
                        )
                        parsed = _parse_cards(cards)
                        if parsed:
                            intercepted.extend(parsed)
                            print(f"[Swiggy] Intercepted {len(parsed)} restaurants")
                    except Exception as e:
                        print(f"[Swiggy] Parse error: {e}")
                    route.fulfill(response=response)
                except Exception as e:
                    print(f"[Swiggy] Route error: {e}")
                    route.continue_()
            else:
                route.continue_()

        page.route("**/*", handle_route)

        try:
            page.goto("https://www.swiggy.com/", wait_until="domcontentloaded", timeout=30000)
            # Wait up to 12s for interception
            page.wait_for_timeout(12000)
        except Exception as e:
            print(f"[Swiggy] Navigation error: {e}")

        # Fallback: in-page fetch with session cookies
        if not intercepted:
            try:
                api_url = (
                    f"https://www.swiggy.com/dapi/restaurants/list/v5"
                    f"?lat={lat}&lng={lng}&is-seo-homepage-enabled=true"
                    f"&page_type=DESKTOP_WEB_LISTING"
                )
                result = page.evaluate(f"""
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
                    intercepted.extend(_parse_cards(cards))
                    print(f"[Swiggy] Fallback got {len(intercepted)} restaurants")
                else:
                    print(f"[Swiggy] Fallback error: {result}")
            except Exception as e:
                print(f"[Swiggy] Fallback exception: {e}")

        browser.close()

    print(f"[Swiggy] Total: {len(intercepted)} restaurants")
    return intercepted


def _sync_fetch_menu(restaurant_id: str, lat: float, lng: float) -> list:
    """Sync Playwright menu scrape."""
    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_stealth_args())
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": lat, "longitude": lng},
            permissions=["geolocation"],
        )
        page = context.new_page()
        _apply_stealth(page)

        def handle_menu(route):
            if "/dapi/menu" in route.request.url:
                try:
                    response = route.fetch()
                    try:
                        body = response.json()
                        for card in body.get("data", {}).get("cards", []):
                            groups = (
                                card.get("groupedCard", {})
                                .get("cardGroupMap", {})
                                .get("REGULAR", {})
                                .get("cards", [])
                            )
                            for g in groups:
                                for ic in g.get("card", {}).get("card", {}).get("itemCards", []):
                                    info = ic.get("card", {}).get("info", {})
                                    if info.get("name"):
                                        items.append({
                                            "id": info.get("id", ""),
                                            "name": info.get("name", ""),
                                            "price": (info.get("price") or 0) / 100,
                                            "is_veg": info.get("itemAttribute", {}).get("vegClassifier") == "VEG",
                                            "description": info.get("description", ""),
                                        })
                    except Exception:
                        pass
                    route.fulfill(response=response)
                except Exception:
                    route.continue_()
            else:
                route.continue_()

        page.route("**/*", handle_menu)
        try:
            page.goto(f"https://www.swiggy.com/restaurants/r-{restaurant_id}",
                      wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(10000)
        except Exception:
            pass

        browser.close()
    return items


# -------------------------------------------------------
# Async wrappers — run sync Playwright in thread pool
# -------------------------------------------------------
async def fetch_swiggy_restaurants(lat: float, lng: float, keyword: str = "") -> list:
    """Async wrapper: runs sync Playwright scrape in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _sync_fetch_restaurants,
        lat, lng, keyword
    )


async def fetch_swiggy_menu(restaurant_id: str, lat: float, lng: float) -> list:
    """Async wrapper: runs sync Playwright menu scrape in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _sync_fetch_menu,
        restaurant_id, lat, lng
    )
