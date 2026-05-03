"""
Zomato Scraper
Uses Playwright (headless Chromium) to intercept Zomato's internal
API calls and extract restaurant + menu data.
"""

import asyncio
import json
import random
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S22) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]

ZOMATOBASE = "https://www.zomato.com"


class ZomatoScraper:
    def __init__(self):
        self.ua = random.choice(USER_AGENTS)

    async def _random_delay(self):
        await asyncio.sleep(random.uniform(1.5, 4.0))

    async def fetch_restaurants(
        self, lat: float, lng: float, cuisine: str = "all"
    ) -> dict:
        """
        Intercept Zomato's search API and return normalised restaurant list.
        """
        results = {"provider": "zomato", "restaurants": [], "error": None}
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.ua,
                    geolocation={"latitude": lat, "longitude": lng},
                    permissions=["geolocation"],
                    viewport={"width": 390, "height": 844},
                )
                page = await context.new_page()
                intercepted = []

                async def handle_response(response):
                    if "api/v1/search" in response.url or "api/v2/restaurants" in response.url:
                        if response.status == 200:
                            try:
                                body = await response.json()
                                intercepted.append(body)
                            except Exception:
                                pass

                page.on("response", handle_response)
                search_url = f"{ZOMATOBASE}/delivery?lat={lat}&lon={lng}"
                if cuisine != "all":
                    search_url += f"&cuisine={cuisine}"
                await page.goto(search_url, wait_until="networkidle", timeout=30000)
                await self._random_delay()

                for payload in intercepted:
                    restaurants = payload.get("restaurants", []) or payload.get("sections", [])
                    for r in restaurants:
                        info = r.get("restaurant", r)
                        if not info.get("id"):
                            continue
                        results["restaurants"].append({
                            "id": str(info.get("id")),
                            "name": info.get("name"),
                            "rating": info.get("user_rating", {}).get("aggregate_rating"),
                            "delivery_time": info.get("order_delivery_time"),
                            "delivery_fee": info.get("min_delivery_fee", 0),
                            "cuisines": [c.strip() for c in info.get("cuisines", "").split(",")],
                            "provider": "zomato",
                        })

                await browser.close()
        except Exception as e:
            results["error"] = str(e)
        return results

    async def fetch_menu(self, restaurant_id: str) -> dict:
        """
        Fetch menu items from a Zomato restaurant page.
        """
        results = {"provider": "zomato", "restaurant_id": restaurant_id, "items": [], "error": None}
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.ua)
                page = await context.new_page()
                intercepted = []

                async def handle_response(response):
                    if "menu" in response.url and response.status == 200:
                        try:
                            body = await response.json()
                            intercepted.append(body)
                        except Exception:
                            pass

                page.on("response", handle_response)
                await page.goto(
                    f"{ZOMATOBASE}/restaurant/{restaurant_id}/order",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await self._random_delay()

                for payload in intercepted:
                    categories = payload.get("sections", {}).get("SECTION_BASIC_INFO", {}).get("menus", [])
                    for cat in categories:
                        for item in cat.get("menu", {}).get("categories", [{}])[0].get("items", []):
                            results["items"].append({
                                "id": str(item.get("item", {}).get("id")),
                                "name": item.get("item", {}).get("name"),
                                "price": item.get("item", {}).get("price", 0),
                                "rating": item.get("item", {}).get("rating"),
                                "is_veg": item.get("item", {}).get("item_tag") == "veg",
                                "category": cat.get("menu", {}).get("name"),
                                "provider": "zomato",
                            })

                await browser.close()
        except Exception as e:
            results["error"] = str(e)
        return results
