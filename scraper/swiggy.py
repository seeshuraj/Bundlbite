# scraper/swiggy.py
# Swiggy scraper with anti-bot bypass
# Strategy: intercept Swiggy's internal API calls via Playwright network interception

import json
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright, Route, Request

# Real Chrome User-Agents — rotate to avoid fingerprinting
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Swiggy's internal API endpoints (intercepted from real browser)
SWIGGY_API_BASE = "https://www.swiggy.com/dapi"


def _stealth_args():
    """Chrome launch args that disable headless detection signals."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-size=1366,768",
        "--start-maximized",
        "--disable-extensions",
        "--disable-gpu",
        "--lang=en-IN",
    ]


async def _apply_stealth(page):
    """Override JS properties that reveal headless Chrome."""
    await page.add_init_script("""
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Fake plugins (real Chrome has plugins, headless has 0)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Fake languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-IN', 'en-US', 'en', 'hi']
        });

        // Fake platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });

        // Chrome runtime object (headless lacks this)
        window.chrome = { runtime: {} };

        // Fix permissions query (headless returns 'denied' by default)
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)


async def fetch_swiggy_restaurants(lat: float, lng: float, keyword: str = "") -> list:
    """
    Fetch restaurants from Swiggy by intercepting their internal dapi calls.
    Two strategies:
    1. API interception (fast, clean JSON)
    2. DOM scraping fallback (slower)
    """
    intercepted_data = []

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
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )

        page = await context.new_page()
        await _apply_stealth(page)

        # --- Strategy 1: Intercept Swiggy's internal dapi network calls ---
        api_event = asyncio.Event()

        async def handle_route(route: Route, request: Request):
            url = request.url
            if "/dapi/restaurants/list" in url or "/dapi/restaurants/search" in url:
                # Let request proceed, capture the response
                response = await route.fetch()
                try:
                    body = await response.json()
                    restaurants = (
                        body.get("data", {}).get("cards", []) or
                        body.get("data", {}).get("restaurants", []) or []
                    )
                    for r in restaurants:
                        info = r.get("card", {}).get("card", {}).get("info", {})
                        if info.get("name"):
                            intercepted_data.append({
                                "id": info.get("id", ""),
                                "name": info.get("name", ""),
                                "cuisines": info.get("cuisines", []),
                                "rating": info.get("avgRatingString", "0"),
                                "delivery_time": info.get("sla", {}).get("deliveryTime", 30),
                                "price_for_two": info.get("costForTwo", "₹300 for two"),
                                "image": info.get("cloudinaryImageId", ""),
                                "source": "swiggy",
                            })
                    api_event.set()
                except Exception:
                    pass
                await route.fulfill(response=response)
            else:
                await route.continue_()

        await page.route("**/*", handle_route)

        # Navigate to Swiggy with location pre-set in URL
        swiggy_url = f"https://www.swiggy.com/city/bangalore/{keyword if keyword else ''}"
        try:
            await page.goto(swiggy_url, wait_until="domcontentloaded", timeout=30000)
            # Wait for API interception (up to 15s)
            try:
                await asyncio.wait_for(api_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass  # Fall through to DOM scraping
        except Exception as e:
            print(f"[Swiggy] Navigation error: {e}")

        # --- Strategy 2: DOM scraping fallback ---
        if not intercepted_data:
            try:
                # Try direct API call with cookies from the page session
                cookies = await context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

                api_url = (
                    f"{SWIGGY_API_BASE}/restaurants/list/v5"
                    f"?lat={lat}&lng={lng}&is-seo-homepage-enabled=true&page_type=DESKTOP_WEB_LISTING"
                )
                api_resp = await page.evaluate(f"""
                    async () => {{
                        const r = await fetch('{api_url}', {{
                            headers: {{
                                'Content-Type': 'application/json',
                                'Cookie': `{cookie_str}`
                            }}
                        }});
                        return await r.json();
                    }}
                """)

                cards = api_resp.get("data", {}).get("cards", [])
                for card in cards:
                    info = card.get("card", {}).get("card", {}).get("info", {})
                    if info.get("name"):
                        intercepted_data.append({
                            "id": info.get("id", ""),
                            "name": info.get("name", ""),
                            "cuisines": info.get("cuisines", []),
                            "rating": info.get("avgRatingString", "0"),
                            "delivery_time": info.get("sla", {}).get("deliveryTime", 30),
                            "price_for_two": info.get("costForTwo", "₹300 for two"),
                            "image": info.get("cloudinaryImageId", ""),
                            "source": "swiggy",
                        })
            except Exception as e:
                print(f"[Swiggy] DOM fallback error: {e}")

        await browser.close()

    return intercepted_data


async def fetch_swiggy_menu(restaurant_id: str, lat: float, lng: float) -> list:
    """Fetch menu items for a specific Swiggy restaurant."""
    items = []

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

        menu_event = asyncio.Event()

        async def handle_menu_route(route: Route, request: Request):
            if "/dapi/menu/pl" in request.url or f"/dapi/restaurants/{restaurant_id}" in request.url:
                response = await route.fetch()
                try:
                    body = await response.json()
                    cards = body.get("data", {}).get("cards", [])
                    for card in cards:
                        groups = card.get("groupedCard", {}).get("cardGroupMap", {}).get("REGULAR", {}).get("cards", [])
                        for g in groups:
                            item_cards = g.get("card", {}).get("card", {}).get("itemCards", [])
                            for ic in item_cards:
                                info = ic.get("card", {}).get("info", {})
                                if info.get("name"):
                                    items.append({
                                        "id": info.get("id", ""),
                                        "name": info.get("name", ""),
                                        "price": info.get("price", 0) / 100,  # paise to rupees
                                        "is_veg": info.get("itemAttribute", {}).get("vegClassifier") == "VEG",
                                        "rating": info.get("ratings", {}).get("aggregatedRating", {}).get("rating", "0"),
                                        "description": info.get("description", ""),
                                        "image": info.get("imageId", ""),
                                    })
                    menu_event.set()
                except Exception:
                    pass
                await route.fulfill(response=response)
            else:
                await route.continue_()

        await page.route("**/*", handle_menu_route)
        url = f"https://www.swiggy.com/restaurants/placeholder-{restaurant_id}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.wait_for(menu_event.wait(), timeout=12)
        except Exception:
            pass

        await browser.close()

    return items
