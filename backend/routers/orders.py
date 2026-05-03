"""
Orders Router
Handles basket optimisation, provider comparison, and deep-link generation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.services.budget import BudgetEngine
import httpx
import os

router = APIRouter()
budget_engine = BudgetEngine()

SCRAPER_URL = os.getenv("SCRAPER_URL", "http://localhost:8001")


class Member(BaseModel):
    name: str
    cuisine: str
    dish_keywords: List[str]
    budget_share: float


class OptimiseRequest(BaseModel):
    members: List[Member]
    total_budget: float
    location: dict = {"lat": 12.9716, "lng": 77.5946}


class BasketConfirmRequest(BaseModel):
    basket_id: str
    provider: str  # "swiggy" | "zomato"
    items: List[dict]


@router.post("/optimise")
async def optimise(req: OptimiseRequest):
    """
    1. Fetch restaurants from both providers via scraper
    2. Run budget optimisation engine
    3. Return top 2 baskets (Swiggy + Zomato best)
    """
    cuisines = ",".join(set(m.cuisine for m in req.members))
    lat = req.location["lat"]
    lng = req.location["lng"]

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.get(
                f"{SCRAPER_URL}/compare",
                params={"lat": lat, "lng": lng, "cuisines": cuisines}
            )
            provider_data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Scraper unavailable: {e}")

    baskets = budget_engine.optimise(
        members=[m.dict() for m in req.members],
        total_budget=req.total_budget,
        swiggy_data=provider_data.get("swiggy", {}),
        zomato_data=provider_data.get("zomato", {}),
    )
    return {"baskets": baskets}


@router.post("/deeplink")
async def generate_deeplink(req: BasketConfirmRequest):
    """
    Generate a deep-link to Swiggy or Zomato app with pre-filled cart.
    This avoids payment liability while delivering full ordering UX.
    """
    if req.provider == "swiggy":
        # Swiggy deep-link format
        link = f"swiggy://restaurant/{req.basket_id}"
        web_fallback = f"https://www.swiggy.com/restaurants/{req.basket_id}"
    elif req.provider == "zomato":
        link = f"zomato://restaurant/{req.basket_id}"
        web_fallback = f"https://www.zomato.com/order/{req.basket_id}"
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

    return {
        "deep_link": link,
        "web_fallback": web_fallback,
        "items_count": len(req.items),
    }
