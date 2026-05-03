"""
Bundlbite Budget Optimisation Engine

Greedy knapsack: for each member, find the best dish match
within their budget share. Minimise delivery fee by co-locating
orders. Score = (rating * 0.4) + (preference_match * 0.4) + (price_fit * 0.2)
"""

from typing import List, Dict, Any
from difflib import SequenceMatcher


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _preference_match(dish_name: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.5
    return max(_similarity(dish_name, kw) for kw in keywords)


def _price_fit(price: float, budget_share: float) -> float:
    if price <= 0 or budget_share <= 0:
        return 0.0
    if price > budget_share:
        return max(0.0, 1.0 - (price - budget_share) / budget_share)
    return 1.0 - (budget_share - price) / budget_share * 0.3  # slight penalty for underspend


def _score_item(item: dict, member: dict, budget_share: float) -> float:
    rating = float(item.get("rating") or 3.5) / 5.0
    pref = _preference_match(item.get("name", ""), member.get("dish_keywords", []))
    price = float(item.get("price") or 0)
    fit = _price_fit(price, budget_share)
    return (rating * 0.4) + (pref * 0.4) + (fit * 0.2)


class BudgetEngine:
    def optimise(
        self,
        members: List[Dict],
        total_budget: float,
        swiggy_data: Dict,
        zomato_data: Dict,
    ) -> List[Dict]:
        """
        Returns top 2 baskets — best from Swiggy, best from Zomato.
        Each basket contains one best-matched item per member.
        """
        per_person_budget = total_budget / len(members) if members else 0
        baskets = []

        for provider_label, provider_data in [("swiggy", swiggy_data), ("zomato", zomato_data)]:
            restaurants = provider_data.get("restaurants", [])
            if not restaurants:
                continue

            # Sort restaurants by rating desc
            restaurants.sort(key=lambda r: float(r.get("rating") or 0), reverse=True)

            basket_items = []
            basket_total = 0
            all_fit = True

            for member in members:
                best_item = None
                best_score = -1

                # Search across top 5 restaurants
                for restaurant in restaurants[:5]:
                    items = restaurant.get("items", [])
                    for item in items:
                        score = _score_item(item, member, per_person_budget)
                        if score > best_score:
                            best_score = score
                            best_item = {
                                **item,
                                "member": member["name"],
                                "restaurant": restaurant["name"],
                                "score": round(score, 3),
                            }

                if best_item:
                    basket_items.append(best_item)
                    basket_total += float(best_item.get("price") or 0)
                else:
                    all_fit = False

            # Estimate delivery fee (avg across restaurants)
            delivery_fee = sum(
                float(r.get("delivery_fee") or 25) for r in restaurants[:3]
            ) / 3
            basket_total += delivery_fee

            avg_rating = (
                sum(float(i.get("rating") or 3.5) for i in basket_items) / len(basket_items)
                if basket_items else 0
            )

            baskets.append({
                "provider": provider_label,
                "items": basket_items,
                "total": round(basket_total, 2),
                "delivery_fee": round(delivery_fee, 2),
                "avg_rating": round(avg_rating, 2),
                "within_budget": basket_total <= total_budget,
                "budget_utilisation": round(basket_total / total_budget * 100, 1) if total_budget else 0,
            })

        # Sort: within-budget first, then by avg_rating
        baskets.sort(key=lambda b: (not b["within_budget"], -b["avg_rating"]))
        return baskets[:2]
