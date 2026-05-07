"""Reranking utilities for retrieved travel knowledge."""

from typing import List

from .knowledge_schema import TravelKnowledgeDoc


def rerank_by_city_and_preferences(
    docs: List[TravelKnowledgeDoc],
    *,
    city: str,
    preferences: List[str],
) -> List[TravelKnowledgeDoc]:
    """Prioritize city-specific and preference-matching documents."""
    preference_text = " ".join(preferences)

    def score(doc: TravelKnowledgeDoc) -> int:
        value = 0
        if city and doc.city == city:
            value += 5
        if not doc.city:
            value += 1
        value += sum(1 for tag in doc.tags if tag and tag in preference_text)
        return value

    return sorted(docs, key=score, reverse=True)
