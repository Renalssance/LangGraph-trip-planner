"""Itinerary feasibility check skill."""

from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, List

from ..models.schemas import TripPlan, TripRequest, WeatherInfo


def check_itinerary(plan: TripPlan, request: TripRequest) -> Dict[str, Any]:
    """Check whether a generated itinerary is executable."""
    issues: List[Dict[str, str]] = []
    suggestions: List[str] = []

    relaxed = _is_relaxed_trip(request)
    max_attractions = 3 if relaxed else 4

    for day in plan.days:
        attraction_count = len(day.attractions)
        if attraction_count > max_attractions:
            issues.append(
                {
                    "type": "overloaded_day",
                    "message": f"Day {day.day_index + 1} 安排了 {attraction_count} 个景点，节奏偏满。",
                }
            )
            suggestions.append(f"压缩 Day {day.day_index + 1} 到 {max_attractions} 个以内核心景点。")

        total_visit_minutes = sum(attraction.visit_duration for attraction in day.attractions)
        if total_visit_minutes > (420 if relaxed else 540):
            issues.append(
                {
                    "type": "time_overload",
                    "message": f"Day {day.day_index + 1} 游玩时长约 {total_visit_minutes} 分钟，缺少交通和休息缓冲。",
                }
            )
            suggestions.append(f"为 Day {day.day_index + 1} 增加午休或删除低优先级点位。")

        max_distance = _max_pairwise_distance_km(day.attractions)
        if max_distance > 18:
            issues.append(
                {
                    "type": "distance_conflict",
                    "message": f"Day {day.day_index + 1} 景点跨度约 {max_distance:.1f} 公里，跨区移动过多。",
                }
            )
            suggestions.append(f"将 Day {day.day_index + 1} 按相邻区域重排，远距离景点拆到其他日期。")

        weather = _weather_for_date(plan.weather_info, day.date)
        if weather and _is_bad_weather(weather) and _outdoor_ratio(day.attractions) >= 0.7:
            issues.append(
                {
                    "type": "weather_conflict",
                    "message": f"Day {day.day_index + 1} 天气可能不适合大量户外景点。",
                }
            )
            suggestions.append(f"为 Day {day.day_index + 1} 增加室内博物馆、展馆或商场备选。")

    score = max(0, 100 - len(issues) * 12)
    return {
        "score": score,
        "issues": issues,
        "suggestions": list(dict.fromkeys(suggestions)),
    }


def _is_relaxed_trip(request: TripRequest) -> bool:
    text = " ".join(request.preferences + [request.free_text_input or ""])
    return any(keyword in text for keyword in ["轻松", "老人", "亲子", "不想太累", "慢"])


def _weather_for_date(weather_info: List[WeatherInfo], date: str) -> WeatherInfo | None:
    return next((item for item in weather_info if item.date == date), None)


def _is_bad_weather(weather: WeatherInfo) -> bool:
    text = f"{weather.day_weather}{weather.night_weather}"
    try:
        hot = int(weather.day_temp) >= 34
    except (TypeError, ValueError):
        hot = False
    return hot or any(keyword in text for keyword in ["雨", "雪", "沙尘", "大风", "雷"])


def _outdoor_ratio(attractions) -> float:
    if not attractions:
        return 0.0
    indoor_keywords = ["博物馆", "美术馆", "商场", "展馆", "剧院", "室内"]
    indoor_count = sum(
        1
        for attraction in attractions
        if any(keyword in f"{attraction.name}{attraction.category}{attraction.description}" for keyword in indoor_keywords)
    )
    return 1 - indoor_count / len(attractions)


def _max_pairwise_distance_km(attractions) -> float:
    max_distance = 0.0
    for index, first in enumerate(attractions):
        for second in attractions[index + 1:]:
            distance = _distance_km(
                first.location.latitude,
                first.location.longitude,
                second.location.latitude,
                second.location.longitude,
            )
            max_distance = max(max_distance, distance)
    return max_distance


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not all([lat1, lon1, lat2, lon2]):
        return 0.0
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(a))
