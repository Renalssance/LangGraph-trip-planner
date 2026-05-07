---
name: preference-matching
description: Score how well a generated travel plan matches user preferences and avoidance requests, returning matched reasons and mismatch issues.
metadata:
  short-description: Match travel preferences
---

# Preference Matching

判断生成行程是否命中用户旅行偏好和规避项，输出匹配分、命中理由和不匹配点。

入口: `backend/app/skill_impls/match_preferences.py::match_preferences`
