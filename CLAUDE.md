# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

这是一个基于 **LangGraph** 框架构建的多智能体旅行规划助手，集成高德地图 MCP 服务和 Vue 3 前端。用户输入目的地、日期和偏好后，系统通过 4 个 LangChain Agent 自动生成包含景点、天气、酒店和每日行程的完整旅行计划。

## 开发命令

### 后端

```bash
cd backend
source ../venv/bin/activate        # 激活已有的虚拟环境
pip install -r requirements.txt    # 安装依赖
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000  # 启动服务
# 或直接: python run.py
```

### 前端

```bash
cd frontend
npm install                        # 安装依赖
npm run dev                        # 开发服务器 (localhost:5173)
npm run build                      # 构建 (vue-tsc + vite build)
npm run preview                    # 预览构建产物
```

Vite 开发服务器会自动将 `/api` 请求代理到后端 `localhost:8000`。

### API 文档

启动后端后访问 `http://localhost:8000/docs` (FastAPI Swagger UI)。

主要端点：
- `POST /api/trip/plan` — 生成旅行计划
- `GET /api/map/poi` — 搜索 POI
- `GET /api/map/weather` — 查询天气
- `POST /api/map/route` — 规划路线
- `GET /api/trip/health` — 健康检查

## 架构概览

### 数据流

```
用户表单(Home.vue) → POST /api/trip/plan → TripPlannerWorkflow.plan_trip()
  → LangGraph StateGraph 执行:
      search_attractions → check_weather → find_hotels → plan_itinerary → END
  → 返回 TripPlan JSON → 前端 Result.vue 渲染(地图+行程+天气+预算)
```

### 后端核心结构

- **`app/api/routes/trip.py`** — FastAPI 路由入口，调用 `workflow.plan_trip(request)`
- **`app/workflows/trip_planner_graph.py`** — LangGraph `StateGraph` 定义，4 个节点的线性工作流 + 条件错误处理
- **`app/workflows/trip_planner_state.py`** — `TripPlannerState` TypedDict，定义节点间传递的状态
- **`app/agents/langgraph_agents.py`** — 4 个 LangChain Agent：attraction search、weather、hotel、planner
- **`app/tools/amap_mcp_tools.py`** — MCP 适配器，通过 `langchain-mcp-adapters` 从 `amap-mcp-server` 加载工具
- **`app/models/schemas.py`** — Pydantic 模型：`TripRequest`、`TripPlan`、`Attraction`、`Meal`、`Hotel` 等
- **`app/services/`** — 单例服务：`llm_service.py`(Dashscope/qwen)、`amap_service.py`、`unsplash_service.py`
- **`app/config.py`** — Pydantic Settings，管理 API 密钥等配置

### 前端核心结构

- **`src/views/Home.vue`** — 表单页（城市、日期、交通/住宿偏好、风格标签）
- **`src/views/Result.vue`** — 结果页（高德地图 JS API 交互、行程展示、导出图片/PDF、编辑模式）
- **`src/services/api.ts`** — Axios 客户端，`generateTripPlan()` / `healthCheck()`
- **`src/types/index.ts`** — TypeScript 接口，与后端 Pydantic 模型对应

### 外部服务集成

| 服务 | 用途 | 配置项 |
|------|------|--------|
| Dashscope (qwen3.5-flash) | LLM 推理 | `DASHSCOPE_API_KEY` |
| amap-mcp-server | 高德地图 MCP 工具(POI/天气/路线) | `AMAP_MAPS_API_KEY` |
| 高德地图 JS API | 前端交互式地图 | `VITE_AMAP_JS_API_KEY` |
| Unsplash API | 景点照片 | `UNSPLASH_ACCESS_KEY` |

## 重要注意事项

### 无用文件

以下文件与项目无关，可忽略：
- `backend/app/workflows/train.py` — Python 基础教程脚本
- `backend/app/agents/old_helloagent_planner_agent.py` — 已废弃的旧 Agent 实现

### LLM 调用方式

项目通过 Dashscope OpenAI 兼容端点 (`https://dashscope.aliyuncs.com/compatible-mode/v1`) 调用 `qwen3.5-flash` 模型，使用 `langchain-openai` 的 `ChatOpenAI` 包装。

### JSON 提取

工作流使用 `_extract_json()` 从 LLM 输出中提取 JSON（支持 markdown code block 和 `{}`/`[]` 分隔符），然后解析为 Pydantic 模型。添加新输出格式时需同步更新此逻辑。

### 单例模式

多个服务使用模块级缓存实现单例（`_llm_instance`、`_amap_service`、`_trip_planner_workflow` 等），首次访问时创建并缓存。

### 测试

项目目前没有配置任何测试框架或测试文件。

---

## LLM 编码行为准则

以下准则用于减少常见的 LLM 编码错误：

### 1. 先思考后编码

- **不要假设，不要隐藏困惑，明确权衡**
- 在实现之前明确陈述假设，如有不确定请提问
- 如果存在多种解释，请呈现它们而不是默默选择
- 如果有更简单的方法，请说出来，必要时提出反对
- 如果不清楚，停下来，指出困惑之处并提问

### 2. 简洁优先

- **只写解决问题的最少代码，不要投机**
- 不添加超出要求的功能
- 不为单次使用创建抽象
- 不添加未请求的"灵活性"或"可配置性"
- 不为不可能的场景添加错误处理
- 如果写了 200 行但可以是 50 行，重写它

### 3. 精准修改

- **只修改必须的部分，只清理自己造成的混乱**
- 不"改进"相邻代码、注释或格式
- 不重构没有问题的代码
- 匹配现有代码风格
- 如果注意到无关的死代码，指出它，不要删除它
- 当你的修改制造了无用代码时，移除它们

### 4. 目标驱动执行

- **定义成功标准，循环直到验证**
- 将任务转化为可验证的目标
- 对于多步骤任务，陈述简要计划
- 设定明确的成功标准以便独立验证
