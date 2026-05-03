"""
Bundlbite Pydantic Schemas
Shared data models used across routers and services.
"""

from pydantic import BaseModel
from typing import List, Optional


class MemberPreference(BaseModel):
    name: str
    cuisine: str
    dish_keywords: List[str] = []
    budget_share: Optional[float] = None
    is_veg: Optional[bool] = None
    dietary_restrictions: List[str] = []


class GroupOrderIntent(BaseModel):
    members: List[MemberPreference]
    total_budget: float
    location: Optional[str] = None
    coordinates: Optional[dict] = None  # {"lat": float, "lng": float}


class MenuItem(BaseModel):
    id: str
    name: str
    price: float
    rating: Optional[float] = None
    is_veg: bool = False
    category: Optional[str] = None
    provider: str  # "swiggy" | "zomato"


class BasketItem(BaseModel):
    member: str
    item: MenuItem
    restaurant: str
    score: float


class Basket(BaseModel):
    provider: str
    items: List[BasketItem]
    total: float
    delivery_fee: float
    avg_rating: float
    within_budget: bool
    budget_utilisation: float
