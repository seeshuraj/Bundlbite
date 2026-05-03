# scraper/main.py
import os
import sys
import json
import asyncio
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from scraper.swiggy import fetch_swiggy_restaurants, fetch_swiggy_menu
from scraper.zomato import fetch_zomato_restaurants, fetch_zomato_menu
from scraper.cache import get_cache, set_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Scraper] Starting up")
    yield
    print("[Scraper] Shutting down")


app = FastAPI(title="Bundlbite Scraper", version="1.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────────────────

def _ok(provider: str, restaurants: list, cached: bool = False) -> dict:
    return {
        "provider": provider,
        "restaurants": restaurants,
        "count": len(restaurants),
        "cached": cached,
        "error": "" if restaurants else f"No results from {provider}",
    }


def _err(provider: str, e: Exception, tb: str) -> JSONResponse:
    print(f"[{provider.upper()} ERROR]\n{tb}")
    return JSONResponse(status_code=200, content={
        "provider": provider,
        "restaurants": [],
        "count": 0,
        "cached": False,
        "error": str(e),
        "traceback": tb,
    })


def _dedup_by_name(restaurants: list) -> list:
    """
    Remove cross-provider duplicates by normalising restaurant names.
    e.g. "McDonald's" appearing from both Swiggy and Zomato -> keep first only.
    """
    seen_names: set[str] = set()
    unique = []
    for r in restaurants:
        # Normalise: lowercase, strip spaces and punctuation for matching
        key = "".join(ch for ch in r.get("name", "").lower() if ch.isalnum())
        if key not in seen_names:
            seen_names.add(key)
            unique.append(r)
    return unique


# ── health ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "platform": sys.platform, "version": "1.2.0"}


# ── swiggy ────────────────────────────────────────────────────────────

@app.get("/swiggy/restaurants")
async def swiggy_restaurants(
    lat: float = Query(...),
    lng: float = Query(...),
    keyword: str = Query(""),
):
    cache_key = f"swiggy:restaurants:{lat:.4f}:{lng:.4f}:{keyword}"
    cached = await get_cache(cache_key)
    if cached:
        data = json.loads(cached)
        return _ok("swiggy", data, cached=True)
    try:
        restaurants = await fetch_swiggy_restaurants(lat, lng, keyword)
        if restaurants:
            await set_cache(cache_key, json.dumps(restaurants), ttl=900)
        return _ok("swiggy", restaurants)
    except Exception as e:
        return _err("swiggy", e, traceback.format_exc())


@app.get("/swiggy/menu")
async def swiggy_menu(
    restaurant_id: str = Query(...),
    lat: float = Query(12.9352),
    lng: float = Query(77.6245),
):
    cache_key = f"swiggy:menu:{restaurant_id}"
    cached = await get_cache(cache_key)
    if cached:
        return {"items": json.loads(cached), "cached": True}
    try:
        items = await fetch_swiggy_menu(restaurant_id, lat, lng)
        if items:
            await set_cache(cache_key, json.dumps(items), ttl=1800)
        return {"restaurant_id": restaurant_id, "items": items, "cached": False}
    except Exception as e:
        return _err("swiggy", e, traceback.format_exc())


# ── zomato ────────────────────────────────────────────────────────────

@app.get("/zomato/restaurants")
async def zomato_restaurants(
    lat: float = Query(...),
    lng: float = Query(...),
    keyword: str = Query(""),
):
    cache_key = f"zomato:restaurants:{lat:.4f}:{lng:.4f}:{keyword}"
    cached = await get_cache(cache_key)
    if cached:
        return _ok("zomato", json.loads(cached), cached=True)
    try:
        restaurants = await fetch_zomato_restaurants(lat, lng, keyword)
        if restaurants:
            await set_cache(cache_key, json.dumps(restaurants), ttl=900)
        return _ok("zomato", restaurants)
    except Exception as e:
        return _err("zomato", e, traceback.format_exc())


@app.get("/zomato/menu")
async def zomato_menu(
    restaurant_id: str = Query(...),
):
    cache_key = f"zomato:menu:{restaurant_id}"
    cached = await get_cache(cache_key)
    if cached:
        return {"items": json.loads(cached), "cached": True}
    try:
        items = await fetch_zomato_menu(restaurant_id)
        if items:
            await set_cache(cache_key, json.dumps(items), ttl=1800)
        return {"restaurant_id": restaurant_id, "items": items, "cached": False}
    except Exception as e:
        return _err("zomato", e, traceback.format_exc())


# ── compare (both providers merged) ───────────────────────────────────

@app.get("/compare")
async def compare(
    lat: float = Query(...),
    lng: float = Query(...),
    keyword: str = Query(""),
):
    """
    Fetch from both Swiggy and Zomato concurrently.
    Returns merged + deduplicated list tagged with source.
    When a keyword is supplied, both scrapers filter by it before merging.
    Cross-provider duplicates (same restaurant name on both platforms) are
    collapsed, keeping the Swiggy entry first (has delivery_time + price).
    """
    swiggy_task = fetch_swiggy_restaurants(lat, lng, keyword)
    zomato_task = fetch_zomato_restaurants(lat, lng, keyword)

    swiggy_results, zomato_results = await asyncio.gather(
        swiggy_task, zomato_task, return_exceptions=True
    )

    if isinstance(swiggy_results, Exception):
        print(f"[Compare] Swiggy error: {swiggy_results}")
        swiggy_results = []
    if isinstance(zomato_results, Exception):
        print(f"[Compare] Zomato error: {zomato_results}")
        zomato_results = []

    # Swiggy first so its richer data (delivery_time, price) wins on dedup
    merged = _dedup_by_name(swiggy_results + zomato_results)

    return {
        "keyword": keyword,
        "swiggy_count": len(swiggy_results),
        "zomato_count": len(zomato_results),
        "total": len(merged),
        "restaurants": merged,
    }
