"""
Swiggy Scraper
Uses Playwright (headless Chromium) to intercept Swiggy's internal
REST API calls and extract restaurant + menu data.
"""

import asyncio
import json
import random
from typing import Optional
from playwright.async_api import async_playwright

# Realistic Android Chrome UA to avoid bot detection
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S22) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
]

SWIGGY_BASE = "https://www.swiggy.com"


class SwiggyScaper:
    def __init__(self):
        self.ua = random.choice(USER_AGENTS)

    async def _random_delay(self):
        await asyncio.sleep(random.uniform(1.5, 3.5))

    async def fetch_restaurants(
        self, lat: float, lng: float, cuisine: str = "all"
    ) -> dict:
        """
        Intercept Swiggy's /dapi/restaurants/list API call.
        Returns normalised list of restaurants with ratings + ETA.
        """
        results = {"provider": "swiggy", "restaurants": [], "error": None}
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
                    if "dapi/restaurants/list" in response.url and response.status == 200:
                        try:
                            body = await response.json()
                            intercepted.append(body)
                        except Exception:
                            pass

                page.on("response", handle_response)
                await page.goto(
                    f"{SWIGGY_BASE}/?lat={lat}&lng={lng}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await self._random_delay()

                if intercepted:
                    raw = intercepted[0]
                    cards = (
                        raw.get("data", {})
                        .get("cards", [])
                    )
                    for card in cards:
                        try:
                            info = (
                                card.get("card", {})
                                .get("card", {})
                                .get("info", {})
                            )
                            if not info.get("id"):
                                continue
                            cuisines = info.get("cuisines", [])
                            # Filter by cuisine if specified
                            if cuisine != "all":
                                match = any(
                                    cuisine.lower() in c.lower()
                                    for c in cuisines
                                )
                                if not match:
                                    continue
                            results["restaurants"].append({
                                "id": info.get("id"),
                                "name": info.get("name"),
                                "rating": info.get("avgRating"),
                                "delivery_time": info.get("sla", {}).get("deliveryTime"),
                                "delivery_fee": info.get("feeDetails", {}).get("totalFee", 0),
                                "cuisines": cuisines,
                                "provider": "swiggy",
                            })
                        except Exception:
                            continue

                await browser.close()
        except Exception as e:
            results["error"] = str(e)
        return results

    async def fetch_menu(self, restaurant_id: str) -> dict:
        """
        Intercept Swiggy's menu API and return normalised item list.
        """
        results = {"provider": "swiggy", "restaurant_id": restaurant_id, "items": [], "error": None}
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.ua)
                page = await context.new_page()
                intercepted = []

                async def handle_response(response):
                    if f"menu?restaurantId={restaurant_id}" in response.url and response.status == 200:
                        try:
                            body = await response.json()
                            intercepted.append(body)
                        except Exception:
                            pass

                page.on("response", handle_response)
                await page.goto(
                    f"{SWIGGY_BASE}/restaurant-menu?restaurantId={restaurant_id}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await self._random_delay()

                if intercepted:
                    cards = (
                        intercepted[0]
                        .get("data", {})
                        .get("cards", [])
                    )
                    for card in cards:
                        try:
                            items = (
                                card.get("groupedCard", {})
                                .get("cardGroupMap", {})
                                .get("REGULAR", {})
                                .get("cards", [])
                            )
                            for item_card in items:
                                item = (
                                    item_card.get("card", {})
                                    .get("card", {})
                                    .get("info", {})
                                )
                                if item.get("id"):
                                    results["items"].append({
                                        "id": item.get("id"),
                                        "name": item.get("name"),
                                        "price": item.get("price", 0) / 100,
                                        "rating": item.get("ratings", {}).get("aggregatedRating", {}).get("rating"),
                                        "is_veg": item.get("itemAttribute", {}).get("vegClassifier") == "VEG",
                                        "category": item.get("category"),
                                        "provider": "swiggy",
                                    })
                        except Exception:
                            continue

                await browser.close()
        except Exception as e:
            results["error"] = str(e)
        return results
