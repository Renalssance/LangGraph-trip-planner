"""Preference matching skill."""

from typing import Any, Dict, List

from ..models.schemas import TripPlan, TripRequest


def match_preferences(plan: TripPlan, request: TripRequest) -> Dict[str, Any]:
    """Score how well a trip plan matches explicit user preferences."""
    preferences = [item for item in request.preferences if item]
    free_text = request.free_text_input or ""
    if not preferences and not free_text:
        return {
            "match_score": 1.0,
            "matched_reasons": ["用户未提供显式偏好，计划按通用旅行质量评估。"],
            "mismatch": [],
        }

    plan_text = _plan_text(plan)
    matched: List[str] = []
    mismatch: List[str] = []

    for preference in preferences:
        if preference in plan_text:
            matched.append(f"计划内容体现了“{preference}”偏好。")
        else:
            mismatch.append(f"未明显体现“{preference}”偏好。")

    avoid_keywords = _extract_avoid_keywords(free_text)
    for keyword in avoid_keywords:
        if keyword in plan_text:
            mismatch.append(f"用户希望避免“{keyword}”，但计划中仍可能出现相关安排。")

    total_checks = max(len(preferences) + len(avoid_keywords), 1)
    passed_checks = max(total_checks - len(mismatch), 0)
    score = round(passed_checks / total_checks, 2)

    return {
        "match_score": score,
        "matched_reasons": matched or ["计划未命中特定偏好词，但保持了基础行程完整性。"],
        "mismatch": mismatch,
    }


def _plan_text(plan: TripPlan) -> str:
    parts = [plan.city, plan.overall_suggestions]
    for day in plan.days:
        parts.extend([day.description, day.transportation, day.accommodation])
        parts.extend(attraction.name + attraction.description + (attraction.category or "") for attraction in day.attractions)
        parts.extend(meal.name + (meal.description or "") for meal in day.meals)
    return " ".join(parts)


def _extract_avoid_keywords(text: str) -> List[str]:
    markers = ["避免", "不想", "不要", "少安排"]
    keywords = []
    for marker in markers:
        if marker in text:
            keywords.append(text.split(marker, 1)[1][:8].strip(" ，,。；;"))
    return [keyword for keyword in keywords if keyword]
