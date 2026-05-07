"""High-level RAG retriever used by the LangGraph workflow."""

from typing import Dict, List

from ..models.schemas import TripRequest
from .ingest import load_seed_knowledge
from .knowledge_schema import TravelKnowledgeDoc
from .reranker import rerank_by_city_and_preferences
from .vector_store import InMemoryTravelKnowledgeStore


class TravelKnowledgeRetriever:
    """Retrieve city, attraction, and preference knowledge for a trip request."""

    def __init__(self, store: InMemoryTravelKnowledgeStore | None = None):
        self.store = store or InMemoryTravelKnowledgeStore(load_seed_knowledge())

    def retrieve_for_request(self, request: TripRequest) -> Dict[str, List[dict]]:
        query = " ".join(
            [
                request.city,
                request.transportation,
                request.accommodation,
                " ".join(request.preferences),
                request.free_text_input or "",
            ]
        )

        city_docs = self._search(query, request, "city", top_k=4)
        attraction_docs = self._search(query, request, "attraction", top_k=4)
        preference_docs = self._search(query, request, "user_preference", top_k=3)
        travel_tips = self._search(query, request, "travel_tip", top_k=3)

        return {
            "retrieved_city_docs": [doc.to_context_dict() for doc in city_docs + travel_tips],
            "retrieved_attraction_docs": [doc.to_context_dict() for doc in attraction_docs],
            "user_profile_context": {
                "preferences": request.preferences,
                "free_text_input": request.free_text_input or "",
                "retrieved_docs": [doc.to_context_dict() for doc in preference_docs],
            },
        }

    def _search(
        self,
        query: str,
        request: TripRequest,
        doc_type: str,
        *,
        top_k: int,
    ) -> List[TravelKnowledgeDoc]:
        docs = self.store.search(query, city=request.city, doc_type=doc_type, top_k=top_k)
        return rerank_by_city_and_preferences(
            docs,
            city=request.city,
            preferences=request.preferences,
        )
