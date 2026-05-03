"""
backend/routers/compare.py
GET /compare?q=biryani&lat=12.9352&lng=77.6245

Fetches restaurants from Zomato and Swiggy in parallel,
merges and returns a unified list sorted by rating.
"""

import asyncio
from fastapi import APIRouter, Query
from typing import Optional

# Scrapers live at project root /scraper/
from scraper.zomato import fetch_zomato_restaurants

# Swiggy scraper — import gracefully so server starts even if not yet implemented
try:
    from scraper.swiggy import fetch_swiggy_restaurants
except ImportError:
    async def fetch_swiggy_restaurants(lat, lng, keyword="", max_results=40):
        return []

router = APIRouter()


def _safe_rating(r: dict) -> float:
    try:
        return float(r.get("rating") or 0)
    except (ValueError, TypeError):
        return 0.0


@router.get("/")
async def compare_restaurants(
    q: str = Query(default="", description="Dish or cuisine keyword"),
    lat: float = Query(default=12.9716, description="Latitude"),
    lng: float = Query(default=77.5946, description="Longitude"),
    max_results: int = Query(default=20, ge=1, le=50),
):
    """
    Returns merged restaurant list from Zomato + Swiggy,
    deduplicated by name and sorted by rating descending.
    """
    zomato_results, swiggy_results = await asyncio.gather(
        fetch_zomato_restaurants(lat, lng, keyword=q, max_results=max_results),
        fetch_swiggy_restaurants(lat, lng, keyword=q, max_results=max_results),
        return_exceptions=True,
    )

    restaurants = []

    if isinstance(zomato_results, list):
        restaurants.extend(zomato_results)
    else:
        print(f"[compare] Zomato error: {zomato_results}")

    if isinstance(swiggy_results, list):
        restaurants.extend(swiggy_results)
    else:
        print(f"[compare] Swiggy error: {swiggy_results}")

    # Deduplicate by normalised name
    seen_names: set[str] = set()
    unique = []
    for r in restaurants:
        key = r.get("name", "").lower().strip()
        if key and key not in seen_names:
            seen_names.add(key)
            unique.append(r)

    # Sort by rating descending
    unique.sort(key=_safe_rating, reverse=True)

    return {
        "query": q,
        "lat": lat,
        "lng": lng,
        "total": len(unique),
        "sources": {
            "zomato": len(zomato_results) if isinstance(zomato_results, list) else 0,
            "swiggy": len(swiggy_results) if isinstance(swiggy_results, list) else 0,
        },
        "restaurants": unique[:max_results],
    }
