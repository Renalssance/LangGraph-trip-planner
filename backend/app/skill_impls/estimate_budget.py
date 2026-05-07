"""Budget estimation skill."""

from typing import Dict

from ..models.schemas import Budget, TripPlan, TripRequest


BUDGET_MULTIPLIERS = {
    "经济": 0.8,
    "经济型": 0.8,
    "标准": 1.0,
    "舒适": 1.15,
    "豪华": 1.8,
    "高端": 1.8,
}


def estimate_budget(plan: TripPlan, request: TripRequest) -> Budget:
    """Estimate a structured budget from the plan and request."""
    multiplier = _budget_multiplier(request.accommodation)
    days_count = max(len(plan.days), request.travel_days, 1)

    total_attractions = sum(
        attraction.ticket_price or 0
        for day in plan.days
        for attraction in day.attractions
    )
    total_hotels = sum(
        day.hotel.estimated_cost
        for day in plan.days
        if day.hotel and day.hotel.estimated_cost
    )
    if total_hotels <= 0:
        total_hotels = int(_default_hotel_cost(request.accommodation) * max(days_count - 1, 1))

    total_meals = sum(
        meal.estimated_cost or 0
        for day in plan.days
        for meal in day.meals
    )
    if total_meals <= 0:
        total_meals = int(160 * days_count * multiplier)

    total_transportation = int(_transportation_daily_cost(request.transportation) * days_count)

    budget = Budget(
        total_attractions=int(total_attractions),
        total_hotels=int(total_hotels),
        total_meals=int(total_meals),
        total_transportation=total_transportation,
        total=0,
    )
    budget.total = (
        budget.total_attractions
        + budget.total_hotels
        + budget.total_meals
        + budget.total_transportation
    )
    return budget


def budget_breakdown(plan: TripPlan, request: TripRequest) -> Dict[str, int]:
    """Return the budget as a plain dictionary."""
    return estimate_budget(plan, request).model_dump()


def _budget_multiplier(accommodation: str) -> float:
    for key, value in BUDGET_MULTIPLIERS.items():
        if key in accommodation:
            return value
    return 1.0


def _default_hotel_cost(accommodation: str) -> int:
    if any(key in accommodation for key in ["豪华", "高端"]):
        return 900
    if any(key in accommodation for key in ["经济", "青旅"]):
        return 280
    return 480


def _transportation_daily_cost(transportation: str) -> int:
    if any(key in transportation for key in ["自驾", "打车", "出租"]):
        return 180
    if any(key in transportation for key in ["步行", "骑行"]):
        return 30
    return 60
