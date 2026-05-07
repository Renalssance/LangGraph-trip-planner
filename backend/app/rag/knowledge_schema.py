"""Schemas for travel knowledge documents."""

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field


KnowledgeDocType = Literal["city", "attraction", "user_preference", "travel_tip"]


class TravelKnowledgeDoc(BaseModel):
    """A searchable travel knowledge record."""

    doc_id: str = Field(..., description="Stable document id")
    doc_type: KnowledgeDocType = Field(..., description="Knowledge category")
    city: str = Field(default="", description="Destination city")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document body")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra structured metadata")

    def searchable_text(self) -> str:
        """Return a compact text representation for lexical retrieval."""
        parts = [self.city, self.title, self.content, " ".join(self.tags)]
        return " ".join(part for part in parts if part)

    def to_context_dict(self) -> Dict[str, Any]:
        """Convert the doc into a serializable context item for workflow state."""
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "city": self.city,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "metadata": self.metadata,
        }
