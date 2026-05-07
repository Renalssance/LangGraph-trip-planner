可以把这个项目从“多 Agent 调 API 生成旅行计划”升级成一个更完整的 **Agentic Travel Planning System**：核心变化是引入 **RAG 提供可靠知识依据**、用 **Skills 沉淀可复用任务能力**，再用 **评估-修正闭环** 保证行程结果可用、可信、可解释。你当前项目已经有 LangGraph 工作流、4 个 LangChain Agent、高德 MCP、FastAPI + Vue 前端，但目前工作流主要是线性的 `search_attractions → check_weather → find_hotels → plan_itinerary`，并且项目说明里也提到暂未配置测试框架，这正好给升级留下空间。

---

## 1. 引入 RAG：让旅行规划不只依赖实时 API 和 LLM 常识

现在系统主要依赖高德 MCP 获取 POI、天气、路线，再让 LLM 生成行程。问题是：LLM 可能不知道景点特色、避坑信息、季节建议、本地交通规则、亲子/情侣/老人适配度等细节。因此可以增加一个 **Travel Knowledge RAG Layer**。

### 可以检索什么内容

建议构建三类知识库：

| 知识库     | 内容                       | 作用                       |
| ------- | ------------------------ | ------------------------ |
| 城市知识库   | 城市概况、热门区域、交通建议、季节特点      | 提高行程合理性                  |
| 景点知识库   | 景点介绍、开放时间、游玩时长、适合人群、避坑建议 | 辅助 attraction agent 筛选景点 |
| 用户偏好知识库 | 用户历史出行偏好、预算、酒店偏好、节奏偏好    | 实现个性化推荐                  |

例如用户输入“东京，3 天，喜欢动漫和美食，不想太累”，系统不应该只找“热门景点”，而应该检索出：

* 秋叶原、池袋、中野 Broadway、三鹰之森吉卜力美术馆等动漫相关地点；
* 浅草、上野、银座、新宿等区域之间的交通距离；
* 每天行程不宜超过 3～4 个核心点；
* 美食推荐应按区域嵌入，而不是独立罗列。

### 推荐新增模块

可以在后端增加：

```text
backend/app/rag/
├── ingest.py              # 文档导入和切分
├── retriever.py           # 向量检索 / 混合检索
├── reranker.py            # 重排序，可选
├── vector_store.py        # Chroma / FAISS / Milvus 封装
└── knowledge_schema.py    # CityDoc / AttractionDoc / TravelTip
```

### 加入 LangGraph 后的工作流

原来的线性流程可以升级成：

```text
parse_user_request
    ↓
retrieve_user_preference
    ↓
retrieve_destination_knowledge
    ↓
search_attractions
    ↓
check_weather
    ↓
find_hotels
    ↓
plan_itinerary
    ↓
evaluate_plan
    ↓
revise_plan_if_needed
    ↓
final_response
```

对应到 `TripPlannerState`，可以增加：

```python
class TripPlannerState(TypedDict):
    request: TripRequest
    retrieved_city_docs: list[dict]
    retrieved_attraction_docs: list[dict]
    user_profile_context: dict
    attractions: list[Attraction]
    weather: dict
    hotels: list[Hotel]
    draft_plan: TripPlan
    evaluation_result: dict
    revision_count: int
    final_plan: TripPlan
```

这样你面试时可以说：

> 我没有简单让 LLM 凭常识生成行程，而是在 LangGraph 中加入 RAG 检索节点，将城市知识、景点知识、用户历史偏好作为外部上下文注入不同 Agent，从而降低幻觉，并提升行程的个性化和可解释性。

---

## 2. 引入 Skills：把“经验型能力”模块化，而不只是调用工具

这里要区分 **Tool** 和 **Skill**：

* **Tool** 更像一个具体 API，例如高德 POI 搜索、天气查询、路线规划。
* **Skill** 更像一个可复用的任务能力，例如“检查行程是否合理”“估算预算”“修复 JSON”“生成旅行报告”。

你的项目已经有 MCP 工具，所以 Skills 不应该重复做 API 调用，而应该封装更高层的 Agent 能力。

### 推荐设计 5 个 Skills

#### Skill 1：Itinerary Feasibility Check

用于检查行程是否真的可执行。

检查内容包括：

* 每天景点数量是否过多；
* 景点之间交通时间是否过长；
* 是否忽略开放时间；
* 是否把距离很远的地点放在同一天；
* 是否符合用户“不想太累”“亲子”“老人”等偏好。

输出示例：

```json
{
  "score": 82,
  "issues": [
    {
      "type": "distance_conflict",
      "message": "Day 2 中新宿到台场距离较远，建议调整顺序或拆分到不同日期。"
    }
  ],
  "suggestions": [
    "将台场移动到 Day 3，并与丰洲市场组合。"
  ]
}
```

#### Skill 2：Budget Estimation

用于估算预算，而不是让 LLM 随便编一个价格。

预算可以拆成：

```text
酒店预算 + 餐饮预算 + 门票预算 + 市内交通预算 + 备用预算
```

并根据用户选择的 budget level 调整：

```text
economy / standard / luxury
```

这个 Skill 可以让项目更像真实产品，而不是简单 demo。

#### Skill 3：Preference Matching

用于判断推荐结果是否符合用户偏好。

例如用户偏好是：

```json
{
  "travel_style": ["美食", "动漫", "轻松"],
  "avoid": ["过度步行", "购物"]
}
```

Skill 输出：

```json
{
  "match_score": 0.87,
  "matched_reasons": [
    "包含秋叶原、池袋等动漫相关区域",
    "每天安排 3 个以内主要地点，节奏较轻松"
  ],
  "mismatch": [
    "Day 1 购物类地点略多"
  ]
}
```

#### Skill 4：JSON Repair / Schema Guard

你现在项目里已经使用 `_extract_json()` 从 LLM 输出中抽取 JSON，再解析成 Pydantic 模型。这个地方很适合升级成一个专门的 Skill。

它负责：

* 修复 markdown 包裹的 JSON；
* 补齐缺失字段；
* 删除多余字段；
* 保证符合 `TripPlan`、`Attraction`、`Hotel` 等 Pydantic schema；
* 如果修复失败，返回明确错误原因。

面试表达可以是：

> 我将 JSON 解析和结构化输出校验从业务逻辑中抽象成独立 Skill，结合 Pydantic schema 做强约束，避免 LLM 输出格式不稳定导致后端接口异常。

#### Skill 5：Report Generation

用于生成最终可读报告，例如：

* Markdown 行程报告；
* PDF 导出文本；
* 每日时间线；
* 地图点位摘要；
* 预算表；
* 注意事项。

这样前端的导出功能会更完整。

---

## 3. 加入评估-修正机制：从“一次生成”变成“生成—审查—修正”

这是最能体现 Agent 项目深度的部分。你可以在 LangGraph 里加入 evaluator agent 和 reviser agent。

### 当前问题

现在的流程大概率是：

```text
搜索 → 查询 → 规划 → 返回
```

这类系统的问题是：

* LLM 生成的行程可能不合理；
* 每天安排可能过满；
* 酒店和景点区域可能不匹配；
* 天气不好时没有替代方案；
* 用户偏好可能没有被充分满足；
* JSON 虽然合法，但内容质量不一定高。

### 推荐升级成闭环

```text
planner_agent 生成 draft_plan
        ↓
evaluator_agent 打分和找问题
        ↓
是否通过？
    ├── 是 → final_plan
    └── 否 → reviser_agent 修正 → 再评估
```

可以设置最多修正 2 次，避免无限循环。

### 评价维度

建议设置一个结构化 evaluation rubric：

| 维度    | 说明                  | 权重  |
| ----- | ------------------- | --- |
| 偏好匹配度 | 是否符合用户主题、预算、节奏      | 25% |
| 地理合理性 | 景点距离、路线顺序是否合理       | 25% |
| 时间可行性 | 每天游玩时长是否过载          | 20% |
| 天气适配性 | 雨天/高温是否有室内方案        | 10% |
| 酒店匹配度 | 酒店位置和预算是否合理         | 10% |
| 输出完整性 | JSON 字段、每日安排、预算是否完整 | 10% |

评价结果示例：

```json
{
  "total_score": 78,
  "pass": false,
  "dimension_scores": {
    "preference_match": 85,
    "geo_reasonability": 65,
    "time_feasibility": 70,
    "weather_adaptation": 60,
    "hotel_match": 80,
    "schema_completeness": 95
  },
  "major_issues": [
    "Day 2 景点分布过散，交通时间过长",
    "雨天仍安排了多个户外景点"
  ],
  "revision_instruction": "压缩 Day 2 的跨区移动，将雨天户外景点替换为室内景点。"
}
```

### LangGraph 条件边设计

可以这样描述：

```python
workflow.add_node("plan_itinerary", plan_itinerary_node)
workflow.add_node("evaluate_plan", evaluate_plan_node)
workflow.add_node("revise_plan", revise_plan_node)

workflow.add_edge("plan_itinerary", "evaluate_plan")

workflow.add_conditional_edges(
    "evaluate_plan",
    should_revise,
    {
        "revise": "revise_plan",
        "finish": END
    }
)

workflow.add_edge("revise_plan", "evaluate_plan")
```

`should_revise` 可以根据分数和修正次数判断：

```python
def should_revise(state: TripPlannerState):
    score = state["evaluation_result"]["total_score"]
    revision_count = state.get("revision_count", 0)

    if score >= 85:
        return "finish"
    if revision_count >= 2:
        return "finish"
    return "revise"
```

这样你可以在简历里写：

> 设计 evaluator-reviser 闭环，通过结构化 rubric 对行程的地理合理性、时间可行性、偏好匹配度、天气适配性进行自动评分，并基于 LangGraph 条件边触发多轮修正，提升生成计划的可靠性。

---

## 4. 最推荐的整体架构升级版

你可以把项目升级后的结构讲成这样：

```text
用户输入
  ↓
Request Parser Agent
  ↓
RAG Retriever
  ├── 城市知识检索
  ├── 景点知识检索
  └── 用户偏好检索
  ↓
Attraction Search Agent  ← 高德 POI MCP
  ↓
Weather Agent            ← 高德天气 MCP
  ↓
Hotel Agent              ← 高德 POI / 酒店检索
  ↓
Planner Agent
  ↓
Skill Layer
  ├── 行程可行性检查 Skill
  ├── 预算估算 Skill
  ├── 用户偏好匹配 Skill
  ├── JSON 修复 Skill
  └── 报告生成 Skill
  ↓
Evaluator Agent
  ↓
Reviser Agent
  ↓
Final TripPlan JSON
  ↓
Vue 前端地图渲染 / 行程展示 / PDF 导出
```

---

## 5. 可以具体怎么改代码目录

建议变成：

```text
backend/app/
├── workflows/
│   ├── trip_planner_graph.py
│   ├── trip_planner_state.py
│   └── evaluation_graph.py
│
├── agents/
│   ├── langgraph_agents.py
│   ├── evaluator_agent.py
│   └── reviser_agent.py
│
├── rag/
│   ├── ingest.py
│   ├── retriever.py
│   ├── vector_store.py
│   └── reranker.py
│
├── skills/
│   ├── itinerary_check/
│   │   ├── SKILL.md
│   │   └── check_itinerary.py
│   ├── budget_estimation/
│   │   ├── SKILL.md
│   │   └── estimate_budget.py
│   ├── json_repair/
│   │   ├── SKILL.md
│   │   └── repair_json.py
│   └── report_generation/
│       ├── SKILL.md
│       └── generate_report.py
│
├── evals/
│   ├── golden_cases.json
│   ├── rubric.py
│   └── run_eval.py
```

---

## 6. 项目亮点可以这样总结成 3 点

### 亮点 1：RAG 增强的多 Agent 旅行规划

在 LangGraph 工作流中引入城市知识、景点知识和用户偏好知识检索，将 RAG 结果作为上下文注入 attraction、hotel 和 planner agent，提升推荐的准确性、个性化和可解释性。

### 亮点 2：Skills 模块化任务能力

将行程可行性检查、预算估算、偏好匹配、JSON 修复和报告生成封装为可复用 Skills，区分底层 MCP 工具调用和高层任务能力，使系统更易扩展和维护。

### 亮点 3：Evaluator-Reviser 自动修正闭环

设计结构化评估机制，从偏好匹配、地理合理性、时间可行性、天气适配、酒店匹配和输出完整性等维度对旅行计划打分，并通过 LangGraph 条件边触发自动修正，避免一次性生成导致的低质量结果。

---

## 7. 简历项目描述可以改成这样

**多 Agent 智能旅行规划助手｜LangGraph / LangChain / RAG / MCP / Vue3 / FastAPI**

* 基于 LangGraph 构建多 Agent 旅行规划工作流，设计景点搜索、天气查询、酒店推荐、行程规划、结果评估与自动修正等节点，并通过条件边实现 evaluator-reviser 闭环优化。
* 引入 RAG 检索增强模块，构建城市攻略、景点知识和用户偏好向量库，将检索结果注入 Planner Agent，提升旅行计划的个性化、事实一致性和可解释性。
* 封装行程可行性检查、预算估算、偏好匹配、JSON Schema 修复和报告生成等 Skills，结合 Pydantic 结构化校验与高德地图 MCP 工具，实现从实时数据查询到高质量行程生成的完整 Agentic Workflow。
