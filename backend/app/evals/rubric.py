"""Structured evaluation rubric for trip plans."""

from typing import Any, Dict, List

from ..models.schemas import TripPlan, TripRequest
from ..skills import check_itinerary, match_preferences


RUBRIC_WEIGHTS = {
    "preference_match": 0.25,
    "geo_reasonability": 0.25,
    "time_feasibility": 0.20,
    "weather_adaptation": 0.10,
    "hotel_match": 0.10,
    "schema_completeness": 0.10,
}


def evaluate_trip_plan(plan: TripPlan, request: TripRequest) -> Dict[str, Any]:
    """Evaluate a trip plan with a structured rubric."""
    feasibility = check_itinerary(plan, request)
    preference = match_preferences(plan, request)
    issues = feasibility["issues"]

    dimension_scores = {
        "preference_match": int(preference["match_score"] * 100),
        "geo_reasonability": _score_without_issue_type(issues, "distance_conflict"),
        "time_feasibility": min(
            feasibility["score"],
            _score_without_issue_type(issues, "time_overload", "overloaded_day"),
        ),
        "weather_adaptation": _score_without_issue_type(issues, "weather_conflict"),
        "hotel_match": _hotel_match_score(plan, request),
        "schema_completeness": _schema_completeness_score(plan, request),
    }

    total_score = round(
        sum(dimension_scores[name] * weight for name, weight in RUBRIC_WEIGHTS.items())
    )
    major_issues = [issue["message"] for issue in issues]
    major_issues.extend(preference["mismatch"])

    suggestions = feasibility["suggestions"]
    if preference["mismatch"]:
        suggestions.append("增加与用户偏好直接相关的景点、餐饮或节奏安排。")

    return {
        "total_score": total_score,
        "pass": total_score >= 85 and not major_issues,
        "dimension_scores": dimension_scores,
        "major_issues": major_issues,
        "revision_instruction": " ".join(dict.fromkeys(suggestions)) or "当前计划质量良好，无需修正。",
        "skill_results": {
            "itinerary_feasibility": feasibility,
            "preference_matching": preference,
        },
    }


def should_revise_plan(evaluation_result: Dict[str, Any], revision_count: int, max_revisions: int = 2) -> bool:
    """Return whether another revision pass should run."""
    if revision_count >= max_revisions:
        return False
    if evaluation_result.get("pass"):
        return False
    return evaluation_result.get("total_score", 0) < 85


def _score_without_issue_type(issues: List[Dict[str, str]], *issue_types: str) -> int:
    count = sum(1 for issue in issues if issue.get("type") in issue_types)
    return max(0, 100 - count * 20)


def _hotel_match_score(plan: TripPlan, request: TripRequest) -> int:
    if not plan.days:
        return 0
    days_with_hotels = sum(1 for day in plan.days if day.hotel or day.accommodation)
    base = int(days_with_hotels / len(plan.days) * 80)
    accommodation_text = " ".join(
        [day.accommodation for day in plan.days]
        + [day.hotel.type for day in plan.days if day.hotel]
        + [day.hotel.price_range for day in plan.days if day.hotel]
    )
    accommodation_keywords = ["经济", "舒适", "标准", "豪华", "高端", "青旅", "民宿", "酒店"]
    if request.accommodation and any(
        keyword in request.accommodation and keyword in accommodation_text
        for keyword in accommodation_keywords
    ):
        base += 20
    return min(base, 100)


def _schema_completeness_score(plan: TripPlan, request: TripRequest) -> int:
    score = 0
    if plan.city and plan.start_date and plan.end_date:
        score += 15
    if len(plan.days) == request.travel_days:
        score += 25
    elif plan.days:
        score += 10
    if all(day.attractions for day in plan.days):
        score += 20
    if all(len(day.meals) >= 3 for day in plan.days):
        score += 15
    if plan.weather_info:
        score += 10
    if plan.budget and plan.budget.total > 0:
        score += 15
    return min(score, 100)
