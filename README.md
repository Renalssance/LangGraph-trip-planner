# 多 Agent 智能旅行助手

基于 LangGraph、LangChain Agent、FastAPI 和 Vue 3 构建的智能旅行规划系统。用户输入目的地、日期、交通方式、住宿偏好和旅行偏好后，系统会通过多 Agent 工作流调用高德地图 MCP 工具、检索旅行知识、生成结构化行程，并通过评估与修订流程提升计划质量。

更完整的 Agent 流程说明见：[agent-flow.md](./agent-flow.md)。

## 功能亮点

- **多 Agent 编排**：使用 LangGraph `StateGraph` 串联景点搜索、天气查询、酒店推荐、行程规划、评估和修订节点。
- **高德地图 MCP 集成**：通过 `amap-mcp-server` 获取 POI、天气、路线等地图服务能力。
- **RAG 旅行知识检索**：内置轻量级旅行知识库，根据城市、偏好和自由文本要求检索城市知识、景点知识和旅行建议。
- **结构化行程输出**：后端返回 Pydantic `TripPlan`，包含每日景点、餐饮、酒店、天气、预算和总体建议。
- **评估与修订闭环**：规划后自动检查偏好匹配、动线合理性、时间可行性、天气适配、住宿匹配和结构完整性；不达标时自动修订。
- **可复用 Skills**：预算估算、JSON 提取、行程可行性检查、偏好匹配、报告生成等逻辑独立封装。
- **前后端完整体验**：Vue 3 + TypeScript 前端支持表单输入、结果页展示、地图标记和行程可视化。

## 技术栈

### 后端

- Python 3.10+
- FastAPI
- LangGraph
- LangChain
- LangChain OpenAI compatible chat model
- langchain-mcp-adapters
- 高德地图 MCP Server
- Pydantic

### 前端

- Vue 3
- TypeScript
- Vite
- Ant Design Vue
- Axios
- 高德地图 JavaScript API
- html2canvas / jsPDF

## 项目结构

```text
LangGraph-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── langgraph_agents.py       # 4 个 LLM Agent 的 prompt 和创建函数
│   │   │   ├── evaluator_agent.py        # 评估器入口
│   │   │   └── reviser_agent.py          # 确定性修订器
│   │   ├── api/
│   │   │   ├── main.py                   # FastAPI 应用入口
│   │   │   └── routes/
│   │   │       ├── trip.py               # 旅行规划接口
│   │   │       ├── map.py                # 地图、天气、路线接口
│   │   │       └── poi.py                # POI 详情和图片接口
│   │   ├── evals/
│   │   │   └── rubric.py                 # 行程评分规则
│   │   ├── models/
│   │   │   └── schemas.py                # 请求和响应模型
│   │   ├── rag/
│   │   │   ├── ingest.py                 # 种子知识加载
│   │   │   ├── knowledge_schema.py       # 知识文档模型
│   │   │   ├── retriever.py              # RAG 检索器
│   │   │   ├── reranker.py               # 检索结果重排
│   │   │   └── vector_store.py           # 轻量内存检索存储
│   │   ├── services/
│   │   │   ├── amap_service.py           # 高德地图服务封装
│   │   │   ├── llm_service.py            # LLM 单例
│   │   │   └── unsplash_service.py       # 景点图片服务
│   │   ├── skill_impls/
│   │   │   ├── check_itinerary.py        # 行程可行性检查
│   │   │   ├── estimate_budget.py        # 预算估算
│   │   │   ├── generate_report.py        # Markdown 报告生成
│   │   │   ├── match_preferences.py      # 偏好匹配
│   │   │   └── repair_json.py            # JSON 提取与修复
│   │   ├── skills/                       # Codex skill bundle 元数据
│   │   ├── tools/
│   │   │   └── amap_mcp_tools.py         # MCP 工具加载、缓存和兜底
│   │   ├── workflows/
│   │   │   ├── trip_planner_graph.py     # LangGraph 工作流主实现
│   │   │   └── trip_planner_state.py     # LangGraph 状态定义
│   │   └── config.py                     # 配置管理
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── services/api.ts               # 前端 API 封装
│   │   ├── types/                        # TypeScript 类型
│   │   └── views/                        # Home / Result 页面
│   ├── package.json
│   └── vite.config.ts
├── agent-flow.md                         # Agent 流程详细文档
└── README.md
```

## 工作流概览

当前旅行规划由 `TripPlannerWorkflow` 构建并编译为 LangGraph：

```text
retrieve_knowledge
  -> search_attractions
  -> check_weather
  -> find_hotels
  -> plan_itinerary
  -> evaluate_plan
      -> revise_plan -> evaluate_plan
      -> END

前置信息节点出错:
  -> handle_error -> END
```

节点说明：

| 节点 | 作用 |
| --- | --- |
| `retrieve_knowledge` | 根据城市、交通、住宿、偏好和自由文本检索 RAG 上下文 |
| `search_attractions` | 景点搜索 Agent 调用高德地图工具，生成 `List[Attraction]` |
| `check_weather` | 天气 Agent 调用天气工具，生成 `List[WeatherInfo]` |
| `find_hotels` | 酒店 Agent 搜索目的地住宿，生成 `List[Hotel]` |
| `plan_itinerary` | 规划 Agent 汇总上下文，生成 `TripPlan` |
| `evaluate_plan` | 按 rubric 对行程打分 |
| `revise_plan` | 根据评估问题自动修订计划，最多 2 轮 |
| `handle_error` | 生成 fallback 计划，避免接口直接失败 |

## 快速开始

### 1. 准备环境

需要安装：

- Python 3.10+
- Node.js 16+
- 高德地图 Web 服务 API Key
- 高德地图 Web 端 JS API Key
- OpenAI 兼容 Chat API Key

后端依赖里会通过 `uvx amap-mcp-server` 连接高德地图 MCP 服务，请确保本机可以正常执行 `uvx`。

### 2. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `backend/.env`，推荐至少配置：

```env
AMAP_API_KEY=your-amap-web-service-key
OPENAI_API_KEY=your-openai-compatible-api-key
OPENAI_BASE_URL=https://your-compatible-endpoint/v1
OPENAI_MODEL=your-model-name
UNSPLASH_ACCESS_KEY=your-unsplash-access-key
UNSPLASH_SECRET_KEY=your-unsplash-secret-key
HOST=0.0.0.0
PORT=8000
```

启动服务：

```bash
python run.py
```

也可以直接运行：

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`
- 旅行规划健康检查：`http://localhost:8000/api/trip/health`

### 3. 启动前端

```bash
cd frontend
npm install
cp .env.example .env
```

编辑 `frontend/.env`：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_WEB_KEY=your-amap-web-service-or-web-key
VITE_AMAP_WEB_JS_KEY=your-amap-js-api-key
```

启动开发服务器：

```bash
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

## 使用流程

1. 在首页填写目的地城市、日期、旅行天数、交通方式、住宿偏好、旅行偏好和补充要求。
2. 点击生成旅行计划。
3. 前端调用 `POST /api/trip/plan`。
4. 后端执行 LangGraph 多 Agent 工作流。
5. 前端把返回的 `TripPlan` 保存到 `sessionStorage` 并跳转到结果页。
6. 结果页展示每日行程、景点、酒店、餐饮、天气、预算和地图标记。

## API 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 根路径，返回服务基本信息 |
| `GET` | `/health` | 应用健康检查 |
| `POST` | `/api/trip/plan` | 生成旅行计划 |
| `GET` | `/api/trip/health` | 旅行规划工作流健康检查 |
| `GET` | `/api/map/poi` | 根据关键词和城市搜索 POI |
| `GET` | `/api/map/weather` | 查询城市天气 |
| `POST` | `/api/map/route` | 规划路线 |
| `GET` | `/api/map/health` | 地图服务健康检查 |
| `GET` | `/api/poi/detail/{poi_id}` | 获取 POI 详情 |
| `GET` | `/api/poi/search` | 搜索 POI |
| `GET` | `/api/poi/photo` | 获取景点图片 |

### 旅行规划请求示例

```bash
curl -X POST http://localhost:8000/api/trip/plan \
  -H "Content-Type: application/json" \
  -d '{
    "city": "北京",
    "start_date": "2026-06-01",
    "end_date": "2026-06-03",
    "travel_days": 3,
    "transportation": "公共交通",
    "accommodation": "经济型酒店",
    "preferences": ["历史文化", "美食"],
    "free_text_input": "希望行程轻松一些，少走回头路"
  }'
```

## 核心代码示例

```python
from app.models.schemas import TripRequest
from app.workflows.trip_planner_graph import get_trip_planner_workflow

workflow = get_trip_planner_workflow()

request = TripRequest(
    city="北京",
    start_date="2026-06-01",
    end_date="2026-06-03",
    travel_days=3,
    transportation="公共交通",
    accommodation="经济型酒店",
    preferences=["历史文化", "美食"],
    free_text_input="希望行程轻松一些，少走回头路",
)

trip_plan = workflow.plan_trip(request)
print(trip_plan.city, len(trip_plan.days), trip_plan.budget.total if trip_plan.budget else 0)
```

## MCP 工具与兜底策略

`backend/app/tools/amap_mcp_tools.py` 会按以下顺序加载工具：

1. 加载完整高德地图 MCP 工具。
2. 如果失败，尝试只加载核心工具，例如 POI 搜索和天气查询。
3. 如果仍失败，使用本地 mock 工具，保证开发环境能跑通流程。

另外，MCP 工具可能只提供异步 `_arun()`。项目通过同步包装器把它适配为可在当前同步 Agent 调用链中使用的工具，避免 FastAPI 事件循环冲突。

## 评估维度

生成计划后，系统会用确定性 rubric 评分：

| 维度 | 权重 |
| --- | ---: |
| 偏好匹配 | 25% |
| 地理动线合理性 | 25% |
| 时间可行性 | 20% |
| 天气适配 | 10% |
| 酒店匹配 | 10% |
| 结构完整性 | 10% |

当总分低于 85 且修订次数未超过上限时，系统会自动进入 `revise_plan` 节点修订，并重新评估。

## 开发提示

- 当前工作流入口是 `backend/app/workflows/trip_planner_graph.py::TripPlannerWorkflow.plan_trip()`。
- Agent prompt 集中在 `backend/app/agents/langgraph_agents.py`。
- LangGraph 状态字段集中在 `backend/app/workflows/trip_planner_state.py`。
- 若要新增 Agent，通常需要新增节点、更新 state 字段、在 `_build_graph()` 中接入边，并补充解析逻辑。
- 若要扩充 RAG 知识，可先修改 `backend/app/rag/ingest.py`，后续可替换为 Chroma、FAISS 或 Milvus。
- 若要调整行程质量标准，优先修改 `backend/app/evals/rubric.py` 和 `backend/app/skill_impls/check_itinerary.py`。
- 生产环境不要把 API Key 写在代码里，应通过 `.env` 或部署平台环境变量注入。

## 常见问题

### MCP 工具加载失败怎么办？

先确认 `AMAP_API_KEY` 是否配置，`uvx amap-mcp-server` 是否能正常运行。如果真实工具不可用，项目会自动降级到 mock 工具，但结果只适合开发调试。

### 为什么生成时间比较久？

一次正常请求至少会调用景点、天气、酒店、规划 4 个 LLM Agent，前三个 Agent 还可能触发多轮工具调用。前端 Axios 超时时间已经设置得较长。

### 为什么计划里可能出现不够真实的坐标或价格？

当前 planner Agent 接收的是部分摘要上下文，不是完整的 POI 和酒店 JSON。更稳妥的改进方向是把完整结构化中间结果注入 planner，或让 planner 只选择和排序真实 POI。

## 许可证

CC BY-NC-SA 4.0

## 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue](https://vuejs.org/)
- [高德地图开放平台](https://lbs.amap.com/)
- [amap-mcp-server](https://github.com/sugarforever/amap-mcp-server)
