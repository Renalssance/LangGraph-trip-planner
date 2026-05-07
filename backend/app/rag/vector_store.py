"""A small pluggable knowledge store.

The current implementation is lexical and dependency-free. It intentionally
keeps the same boundary a vector database wrapper would expose, so Chroma,
FAISS, or Milvus can replace it without changing workflow code.
"""

from collections import Counter
import math
import re
from typing import Iterable, List, Optional

from .knowledge_schema import KnowledgeDocType, TravelKnowledgeDoc


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    """Tokenize English and CJK text for lightweight matching."""
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class InMemoryTravelKnowledgeStore:
    """Dependency-free searchable store for travel knowledge documents."""

    def __init__(self, docs: Optional[Iterable[TravelKnowledgeDoc]] = None):
        self.docs: List[TravelKnowledgeDoc] = list(docs or [])

    def add_documents(self, docs: Iterable[TravelKnowledgeDoc]) -> None:
        self.docs.extend(docs)

    def search(
        self,
        query: str,
        *,
        city: str = "",
        doc_type: Optional[KnowledgeDocType] = None,
        top_k: int = 5,
    ) -> List[TravelKnowledgeDoc]:
        query_tokens = tokenize(f"{city} {query}")
        if not query_tokens:
            return []

        query_counter = Counter(query_tokens)
        scored: List[tuple[float, TravelKnowledgeDoc]] = []
        for doc in self.docs:
            if doc_type and doc.doc_type != doc_type:
                continue

            doc_tokens = tokenize(doc.searchable_text())
            if not doc_tokens:
                continue

            doc_counter = Counter(doc_tokens)
            overlap = sum(min(query_counter[token], doc_counter[token]) for token in query_counter)
            if city and city in doc.city:
                overlap += 2
            if any(tag in query for tag in doc.tags):
                overlap += 1

            if overlap <= 0:
                continue

            norm = math.sqrt(sum(v * v for v in doc_counter.values())) or 1.0
            scored.append((overlap / norm, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]
