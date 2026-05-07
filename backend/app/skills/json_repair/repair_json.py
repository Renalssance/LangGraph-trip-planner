"""JSON repair and schema guard skill."""

from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, ValidationError


def extract_json(response: str) -> str:
    """Extract the first likely JSON object or array from an LLM response."""
    text = response.strip()
    if "```json" in text:
        json_start = text.find("```json") + 7
        json_end = text.find("```", json_start)
        if json_end != -1:
            return text[json_start:json_end].strip()
    if "```" in text:
        json_start = text.find("```") + 3
        json_end = text.find("```", json_start)
        if json_end != -1:
            return text[json_start:json_end].strip()

    starts = [index for index in [text.find("{"), text.find("[")] if index != -1]
    if not starts:
        return text

    start = min(starts)
    end_char = "}" if text[start] == "{" else "]"
    end = text.rfind(end_char)
    if end == -1:
        return text[start:]
    return text[start:end + 1]


def load_repaired_json(response: str) -> Any:
    """Load JSON after common LLM formatting repairs."""
    json_str = extract_json(response)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        repaired = (
            json_str
            .replace("，", ",")
            .replace("：", ":")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        return json.loads(repaired)


def repair_and_validate_json(response: str, schema: Type[BaseModel]) -> BaseModel:
    """Parse, lightly repair, and validate an LLM JSON response against a schema."""
    data = load_repaired_json(response)
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"JSON does not match {schema.__name__}: {exc}") from exc
