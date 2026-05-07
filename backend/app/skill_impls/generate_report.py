"""Report generation skill."""

from ..models.schemas import TripPlan


def generate_trip_report(plan: TripPlan) -> str:
    """Generate a concise Markdown trip report."""
    lines = [
        f"# {plan.city}旅行计划",
        "",
        f"日期: {plan.start_date} 至 {plan.end_date}",
        "",
    ]

    for day in plan.days:
        lines.extend(
            [
                f"## Day {day.day_index + 1}｜{day.date}",
                day.description,
                "",
                f"- 交通: {day.transportation}",
                f"- 住宿: {day.hotel.name if day.hotel else day.accommodation}",
                f"- 景点: {', '.join(attraction.name for attraction in day.attractions) or '待补充'}",
                f"- 餐饮: {', '.join(meal.name for meal in day.meals) or '待补充'}",
                "",
            ]
        )

    if plan.budget:
        lines.extend(
            [
                "## 预算",
                f"- 景点: {plan.budget.total_attractions} 元",
                f"- 酒店: {plan.budget.total_hotels} 元",
                f"- 餐饮: {plan.budget.total_meals} 元",
                f"- 交通: {plan.budget.total_transportation} 元",
                f"- 合计: {plan.budget.total} 元",
                "",
            ]
        )

    lines.extend(["## 建议", plan.overall_suggestions])
    return "\n".join(lines)
