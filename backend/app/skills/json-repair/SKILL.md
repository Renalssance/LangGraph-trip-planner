---
name: json-repair
description: Extract, repair, and validate JSON returned by LLMs, including Markdown-wrapped JSON and common punctuation issues, then guard it with Pydantic schemas.
metadata:
  short-description: Repair and validate JSON
---

# JSON Repair / Schema Guard

从 LLM 输出中提取 JSON，修复常见中文标点和 Markdown 包裹，并用 Pydantic schema 校验。

入口: `backend/app/skill_impls/repair_json.py::extract_json` 和 `backend/app/skill_impls/repair_json.py::repair_and_validate_json`
