---
name: itinerary-check
description: Check whether a generated travel itinerary is executable by reviewing daily attraction count, visit duration, route distance, weather adaptation, and pacing preferences.
metadata:
  short-description: Check itinerary feasibility
---

# Itinerary Feasibility Check

检查每日景点数量、游玩时长、跨区距离和天气适配性，输出分数、问题列表和修正建议。

入口: `backend/app/skill_impls/check_itinerary.py::check_itinerary`
