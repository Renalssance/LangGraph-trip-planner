"""Deterministic reviser agent for travel plans."""

from typing import Any, Dict

from ..models.schemas import Meal, TripPlan, TripRequest
from ..skills import estimate_budget


def revise_plan(plan: TripPlan, request: TripRequest, evaluation_result: Dict[str, Any]) -> TripPlan:
    """Revise a plan according to evaluator feedback without another LLM call."""
    revised = plan.model_copy(deep=True)
    issues = evaluation_result.get("skill_results", {}).get("itinerary_feasibility", {}).get("issues", [])
    issue_types = {issue.get("type") for issue in issues}

    for day in revised.days:
        if {"overloaded_day", "time_overload"} & issue_types and len(day.attractions) > 3:
            day.attractions = day.attractions[:3]
            day.description = f"{day.description} 已压缩为更轻松的核心点位。"

        if "weather_conflict" in issue_types:
            day.description = f"{day.description} 天气不佳时优先切换为室内展馆、商场或美食体验。"

        _ensure_three_meals(day)

    instruction = evaluation_result.get("revision_instruction", "")
    if instruction and instruction not in revised.overall_suggestions:
        revised.overall_suggestions = f"{revised.overall_suggestions}\n修正说明: {instruction}"

    revised.budget = estimate_budget(revised, request)
    return revised


def _ensure_three_meals(day) -> None:
    existing_types = {meal.type for meal in day.meals}
    defaults = [
        Meal(type="breakfast", name="当地早餐", description="选择酒店附近或当天首个景点附近的早餐。", estimated_cost=30),
        Meal(type="lunch", name="区域午餐", description="结合上午和下午景点所在区域安排午餐。", estimated_cost=60),
        Meal(type="dinner", name="特色晚餐", description="选择当天住宿或返程动线附近的特色晚餐。", estimated_cost=90),
    ]
    for meal in defaults:
        if meal.type not in existing_types:
            day.meals.append(meal)
