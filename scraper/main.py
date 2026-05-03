"""
Bundlbite Scraper Microservice
FastAPI app exposing menu + pricing endpoints.
Playwright fetches live data; Redis caches results.
"""

from fastapi import FastAPI, HTTPException, Query
from scraper.swiggy import SwiggyScaper
from scraper.zomato import ZomatoScraper
from scraper.cache import RedisCache
import asyncio

app = FastAPI(title="Bundlbite Scraper", version="1.0.0")
cache = RedisCache()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/swiggy/restaurants")
async def swiggy_restaurants(
    lat: float = Query(...),
    lng: float = Query(...),
    cuisine: str = Query(default="all")
):
    cache_key = f"swiggy:restaurants:{lat}:{lng}:{cuisine}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    scraper = SwiggyScaper()
    data = await scraper.fetch_restaurants(lat, lng, cuisine)
    await cache.set(cache_key, data, ttl=900)  # 15 min TTL
    return data


@app.get("/swiggy/menu/{restaurant_id}")
async def swiggy_menu(restaurant_id: str):
    cache_key = f"swiggy:menu:{restaurant_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    scraper = SwiggyScaper()
    data = await scraper.fetch_menu(restaurant_id)
    await cache.set(cache_key, data, ttl=900)
    return data


@app.get("/zomato/restaurants")
async def zomato_restaurants(
    lat: float = Query(...),
    lng: float = Query(...),
    cuisine: str = Query(default="all")
):
    cache_key = f"zomato:restaurants:{lat}:{lng}:{cuisine}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    scraper = ZomatoScraper()
    data = await scraper.fetch_restaurants(lat, lng, cuisine)
    await cache.set(cache_key, data, ttl=900)
    return data


@app.get("/zomato/menu/{restaurant_id}")
async def zomato_menu(restaurant_id: str):
    cache_key = f"zomato:menu:{restaurant_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    scraper = ZomatoScraper()
    data = await scraper.fetch_menu(restaurant_id)
    await cache.set(cache_key, data, ttl=900)
    return data


@app.get("/compare")
async def compare(
    lat: float = Query(...),
    lng: float = Query(...),
    cuisines: str = Query(..., description="Comma-separated list of cuisines")
):
    """Fetch and normalise restaurants from both providers in parallel."""
    cuisine_list = [c.strip() for c in cuisines.split(",")]
    tasks = [
        SwiggyScaper().fetch_restaurants(lat, lng, " ".join(cuisine_list)),
        ZomatoScraper().fetch_restaurants(lat, lng, " ".join(cuisine_list)),
    ]
    swiggy_data, zomato_data = await asyncio.gather(*tasks)
    return {
        "swiggy": swiggy_data,
        "zomato": zomato_data,
    }
