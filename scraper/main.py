# scraper/main.py
import os
import json
import traceback
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from scraper.swiggy import fetch_swiggy_restaurants, fetch_swiggy_menu
from scraper.cache import get_cache, set_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Scraper] Starting up — Playwright ready")
    yield
    print("[Scraper] Shutting down")


app = FastAPI(title="Bundlbite Scraper", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/swiggy/restaurants")
async def swiggy_restaurants(
    lat: float = Query(...),
    lng: float = Query(...),
    keyword: str = Query(""),
):
    cache_key = f"swiggy:restaurants:{lat:.4f}:{lng:.4f}:{keyword}"
    cached = await get_cache(cache_key)
    if cached:
        return {"provider": "swiggy", "restaurants": json.loads(cached), "cached": True}

    try:
        restaurants = await fetch_swiggy_restaurants(lat, lng, keyword)
        if restaurants:
            await set_cache(cache_key, json.dumps(restaurants), ttl=900)
        return {
            "provider": "swiggy",
            "restaurants": restaurants,
            "count": len(restaurants),
            "cached": False,
            "error": "" if restaurants else "No results — Swiggy may be blocking scraper",
        }
    except Exception as e:
        # Return detailed error instead of 500
        tb = traceback.format_exc()
        print(f"[Scraper ERROR]\n{tb}")
        return JSONResponse(
            status_code=200,  # Return 200 with error details so UI can handle gracefully
            content={
                "provider": "swiggy",
                "restaurants": [],
                "count": 0,
                "cached": False,
                "error": str(e),
                "traceback": tb,
            },
        )


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
        tb = traceback.format_exc()
        print(f"[Menu ERROR]\n{tb}")
        return JSONResponse(
            status_code=200,
            content={"restaurant_id": restaurant_id, "items": [], "error": str(e), "traceback": tb},
        )


@app.get("/compare")
async def compare(
    lat: float = Query(...),
    lng: float = Query(...),
    keyword: str = Query(""),
):
    swiggy_results = await fetch_swiggy_restaurants(lat, lng, keyword)
    return {
        "swiggy": swiggy_results,
        "swiggy_count": len(swiggy_results),
    }
