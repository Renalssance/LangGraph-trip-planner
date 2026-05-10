# 多 Agent 智能旅行助手

基于 FastAPI、LangGraph、LangChain Agent 和 Vue 3 的智能旅行规划系统。用户填写目的地、日期、交通方式、住宿偏好、旅行偏好和补充要求后，前端通过流式接口接收真实 LangGraph 节点进度，后端调用高德地图 MCP 工具、检索内置旅行知识、生成结构化行程，并通过评估与修订流程提升计划质量。

更完整的 Agent 流程说明见：[agent-flow.md](./agent-flow.md)。

## 功能亮点

- **LangGraph 多节点编排**：`retrieve_knowledge -> search_attractions -> check_weather -> find_hotels -> plan_itinerary -> evaluate_plan`，必要时进入 `revise_plan`。
- **流式进度反馈**：前端默认调用 `POST /api/trip/plan/stream`，实时展示请求接收、工具准备、知识检索、景点搜索、天气查询、酒店搜索、规划、评估和修订进度。
- **高德地图 MCP 集成**：通过 `amap-mcp-server` 获取 POI、天气、地理编码等能力；真实工具不可用时自动降级到本地 mock 工具。
- **RAG 旅行知识检索**：内置轻量知识库，按城市、偏好和自由文本检索城市动线、景点知识、天气适配和用户偏好建议。
- **结构化行程输出**：后端返回 Pydantic `TripPlan`，包含每日景点、餐饮、酒店、天气、预算和总体建议。
- **评估与修订闭环**：按偏好匹配、地理动线、时间可行性、天气适配、酒店匹配和结构完整性打分；低于阈值时最多自动修订 2 轮。
- **可复用 Skills**：JSON 提取、预算估算、行程可行性检查、偏好匹配、Markdown 报告生成等逻辑独立封装。
- **前后端完整体验**：Vue 3 + TypeScript 前端支持表单输入、进度列表、结果页展示、地图标记、图片补充和 PDF 导出。

## 技术栈

后端：

- Python 3.10-3.12
- FastAPI / Uvicorn
- LangGraph
- LangChain 1.x
- `langchain-openai` OpenAI 兼容 Chat 模型
- `langchain-mcp-adapters`
- Pydantic v2

前端：

- Vue 3
- TypeScript
- Vite
- Ant Design Vue
- Axios / Fetch SSE
- 高德地图 JavaScript API
- html2canvas / jsPDF

## 项目结构

```text
LangGraph-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── langgraph_agents.py       # 景点、天气、酒店、规划 Agent
│   │   │   ├── evaluator_agent.py        # 评估器入口
│   │   │   └── reviser_agent.py          # 确定性修订器
│   │   ├── api/
│   │   │   ├── main.py                   # FastAPI 应用入口
│   │   │   └── routes/
│   │   │       ├── trip.py               # 普通规划接口和 SSE 流式接口
│   │   │       ├── map.py                # 地图、天气、路线接口
│   │   │       └── poi.py                # POI 详情和图片接口
│   │   ├── evals/
│   │   │   └── rubric.py                 # 行程评分规则
│   │   ├── models/
│   │   │   └── schemas.py                # 请求和响应模型
│   │   ├── rag/
│   │   │   ├── ingest.py                 # 内置种子知识
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
│   │   ├── skills/                       # Skill 元数据
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
│   │   ├── services/api.ts               # 普通 API 和 SSE 流式 API 封装
│   │   ├── types/                        # TypeScript 类型
│   │   └── views/                        # Home / Result 页面
│   ├── package.json
│   └── vite.config.ts
├── agent-flow.md
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

retrieve_knowledge / search_attractions / check_weather / find_hotels 出错:
  -> handle_error -> END
```

节点说明：

| 节点 | 作用 |
| --- | --- |
| `retrieve_knowledge` | 根据城市、交通、住宿、偏好和自由文本检索 RAG 上下文 |
| `search_attractions` | 景点搜索 Agent 调用高德地图工具，解析为 `List[Attraction]` |
| `check_weather` | 天气 Agent 调用天气工具，解析为 `List[WeatherInfo]` |
| `find_hotels` | 酒店 Agent 搜索住宿，解析为 `List[Hotel]`；未解析到酒店时继续规划 |
| `plan_itinerary` | 规划 Agent 汇总上下文，生成 `TripPlan`，并补预算、生成报告 |
| `evaluate_plan` | 按 rubric 对行程打分 |
| `revise_plan` | 根据评估问题自动修订计划，最多 2 轮 |
| `handle_error` | 前置信息节点失败时生成 fallback 计划 |

注意：`plan_itinerary` 解析 JSON 失败时会生成 fallback 计划；如果规划节点整体异常且没有计划产物，普通接口会返回 500，流式接口会发送 `error` 事件。

## 快速开始

### 1. 准备环境

需要安装：

- Python 3.10-3.12
- Node.js 16+
- 高德地图 Web 服务 API Key
- 高德地图 Web 端 JS API Key
- OpenAI 兼容 Chat API Key
- `uv` / `uvx`，用于启动 `amap-mcp-server`

### 2. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `backend/.env`，当前代码实际读取这些 LLM 变量：

```env
AMAP_API_KEY=your-amap-web-service-key
LLM_API_KEY=your-openai-compatible-api-key
LLM_BASE_URL=https://your-compatible-endpoint/v1
LLM_MODEL_ID=your-model-name
LLM_TIMEOUT=60
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

1. 首页填写目的地城市、日期、旅行天数、交通方式、住宿偏好、旅行偏好和补充要求。
2. 点击生成旅行计划。
3. 前端调用 `streamTripPlan()`，请求 `POST /api/trip/plan/stream`。
4. 后端通过 SSE 持续返回 `progress`、`complete` 或 `error` 事件。
5. 前端展示进度条和最近 12 条进度日志。
6. 收到 `complete` 后把 `TripPlan` 保存到 `sessionStorage`，跳转结果页。
7. 结果页展示每日行程、景点、酒店、餐饮、天气、预算、地图标记和图片。

## API 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 根路径，返回服务基本信息 |
| `GET` | `/health` | 应用健康检查 |
| `POST` | `/api/trip/plan` | 同步生成旅行计划 |
| `POST` | `/api/trip/plan/stream` | 流式生成旅行计划，返回 SSE 进度和最终结果 |
| `GET` | `/api/trip/health` | 旅行规划工作流健康检查 |
| `GET` | `/api/map/poi` | 根据关键词和城市搜索 POI |
| `GET` | `/api/map/weather` | 查询城市天气 |
| `POST` | `/api/map/route` | 规划路线 |
| `GET` | `/api/map/health` | 地图服务健康检查 |
| `GET` | `/api/poi/detail/{poi_id}` | 获取 POI 详情 |
| `GET` | `/api/poi/search` | 搜索 POI |
| `GET` | `/api/poi/photo` | 获取景点图片 |

### 同步请求示例

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

### 流式请求示例

```bash
curl -N -X POST http://localhost:8000/api/trip/plan/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "city": "上海",
    "start_date": "2026-06-01",
    "end_date": "2026-06-02",
    "travel_days": 2,
    "transportation": "公共交通",
    "accommodation": "舒适型酒店",
    "preferences": ["城市漫步", "美食"],
    "free_text_input": "希望晚上看夜景"
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
2. 如果失败，尝试只加载核心工具，例如 `maps_text_search` 和 `maps_weather`。
3. 如果仍失败，使用本地 mock 工具，保证开发环境能跑通流程。

部分 MCP 工具只提供异步 `_arun()`。项目通过同步包装器把它适配到当前同步 Agent 调用链中；如果 FastAPI 线程里已有事件循环，会在线程池中运行 coroutine，避免事件循环冲突。

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

- 当前工作流入口是 `backend/app/workflows/trip_planner_graph.py::TripPlannerWorkflow.plan_trip()` 和 `plan_trip_with_progress()`。
- 前端默认入口是 `frontend/src/services/api.ts::streamTripPlan()`。
- Agent prompt 集中在 `backend/app/agents/langgraph_agents.py`。
- LangGraph 状态字段集中在 `backend/app/workflows/trip_planner_state.py`。
- 进度条文案和百分比集中在 `backend/app/workflows/trip_planner_graph.py::PROGRESS_NODE_META`。
- 若要新增 Agent，通常需要新增节点、更新 state 字段、在 `_build_graph()` 中接入边，并补充解析逻辑。
- 若要扩充 RAG 知识，可先修改 `backend/app/rag/ingest.py`，后续可替换为 Chroma、FAISS 或 Milvus。
- 若要调整行程质量标准，优先修改 `backend/app/evals/rubric.py` 和 `backend/app/skill_impls/check_itinerary.py`。
- 生产环境不要把 API Key 写在代码里，应通过 `.env` 或部署平台环境变量注入。

## 常见问题

### MCP 工具加载失败怎么办？

先确认 `AMAP_API_KEY` 是否配置，`uvx amap-mcp-server` 是否能正常运行。如果真实工具不可用，项目会自动降级到 mock 工具，但结果只适合开发调试。

### 为什么生成时间比较久？

一次正常请求会调用景点、天气、酒店、规划等多个 Agent，前三个 Agent 还可能触发工具调用。前端现在使用流式接口展示中间进度，普通同步接口的 Axios 超时时间也设置得较长。

### 为什么计划里可能出现不够真实的坐标或价格？

当前 planner Agent 接收的是摘要化中间结果，不是完整 POI 和酒店 JSON。解析阶段会尝试用地理编码补坐标，预算也会通过 skill 补全，但最稳妥的改进方向是把完整结构化候选项注入 planner，或让 planner 只选择真实候选 POI。

## 许可证

CC BY-NC-SA 4.0

## 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Vue](https://vuejs.org/)
- [高德地图开放平台](https://lbs.amap.com/)
- [amap-mcp-server](https://github.com/sugarforever/amap-mcp-server)
