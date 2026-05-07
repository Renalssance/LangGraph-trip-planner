"""Evaluator agent facade for travel plans."""

from typing import Any, Dict

from ..evals import evaluate_trip_plan
from ..models.schemas import TripPlan, TripRequest


def evaluate_plan(plan: TripPlan, request: TripRequest) -> Dict[str, Any]:
    """Evaluate a generated trip plan."""
    return evaluate_trip_plan(plan, request)
