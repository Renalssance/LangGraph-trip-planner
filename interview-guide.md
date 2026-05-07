# 多 Agent 智能旅行助手 — 面试问答指南

## 一、项目概述（自我介绍 / 一分钟电梯演讲）

**Q: 简单介绍一下你的这个项目？**

**A:** 这是一个基于 LangGraph 框架构建的多 Agent 旅行规划系统。用户输入目的地城市、日期、交通/住宿偏好后，系统通过 4 个专门化的 LangChain Agent（景点搜索、天气查询、酒店推荐、行程规划）协作，调用高德地图 MCP 工具获取真实 POI、天气和路线数据，最终生成包含每日行程、天气、预算的完整旅行计划。前端用 Vue 3 + TypeScript + 高德地图 JS API 实现交互式地图展示和行程可视化。

核心技术栈：
- **后端**: Python + FastAPI + LangGraph + LangChain + MCP
- **Agent 框架**: LangGraph StateGraph，4 节点线性工作流 + 条件错误路由
- **工具层**: amap-mcp-server（高德地图 MCP 服务），langchain-mcp-adapters 桥接
- **LLM**: 通义千问 qwen3.5-flash（Dashscope OpenAI 兼容端点）
- **前端**: Vue 3 + TypeScript + Ant Design Vue + 高德地图 JS API

---

## 二、LangGraph 框架相关

### Q1: 为什么选择 LangGraph？它和普通 LangChain Chain 有什么区别？

**A:** 普通 LangChain Chain 是线性的、固定流程的，而 LangGraph 提供了**状态图（StateGraph）** 的抽象，核心优势：

1. **状态共享**: 所有节点通过一个共享的 `State`（TypedDict）通信，每个节点只更新自己负责的字段，避免显式传递参数
2. **条件路由**: 可以用 `add_conditional_edges` 实现分支逻辑（比如错误检测后跳转到错误处理节点）
3. **可组合性**: 节点本身可以是另一个子图（subgraph），方便嵌套和复用
4. **可观测性**: 内置 checkpoint 机制，支持中断、恢复、回放

在本项目中，我定义了 `TripPlannerState`，包含 `request`、`attractions`、`weather_info`、`hotels`、`trip_plan`、`error` 等字段。每个节点只更新自己负责的字段，LangGraph 自动合并状态。

### Q2: 你的工作流图是怎么设计的？

**A:** 采用 **线性流水线 + 条件错误路由** 的拓扑结构：

```
ENTRY → search_attractions → check_weather → find_hotels → plan_itinerary → END
              |                    |               |
              +--(error?)→ handle_error ───────────+
```

- **入口节点**: `search_attractions`
- **正常边**: 4 个主节点依次执行
- **条件边**: 每个主节点执行后，通过 `_check_error(state)` 判断 `state["error"]` 是否存在
  - `continue` → 下一个正常节点
  - `error` → `handle_error` 节点（生成 fallback 计划）
- **终态**: `plan_itinerary` 完成或 `handle_error` 完成后都到 `END`

代码中用 `workflow.add_conditional_edges()` 在每个节点后挂载错误检查逻辑。

### Q3: StateGraph 的 `Annotated` 字段（如 `messages: Annotated[List[Dict], add_messages]`）是什么意思？

**A:** 这是 LangGraph 的 **reducer** 机制。默认情况下，如果节点返回一个字典中某个键的值，会直接覆盖之前的值。但用 `Annotated[type, reducer_fn]` 可以自定义合并策略。

- `add_messages` 是 LangGraph 内置的 reducer，会把新消息 **追加** 到已有消息列表后面，而不是覆盖
- `current_step` 用了自定义的 `update_step` 函数，总是用新值替换旧值，用于追踪当前步骤

这样设计避免了在节点里手动合并 messages 列表的样板代码。

### Q4: 工作流的状态是怎么传递的？节点之间怎么共享数据？

**A:** 所有节点共享同一个 `TripPlannerState` TypedDict。每个节点函数接收 `state` 参数，返回一个 **部分更新字典**（只包含要修改的字段），LangGraph 自动合并。

比如 `_search_attractions` 节点：
```python
def _search_attractions(self, state):
    ...
    return {
        "attractions": attractions,  # 只更新 attractions 字段
        "messages": [{"role": "assistant", "content": "..."}]
    }
```

后续节点（如 `_check_weather`）可以通过 `state["attractions"]` 访问到前面节点写入的数据。`plan_itinerary` 节点则读取所有前置节点的结果（attractions、weather、hotels）来生成最终行程。

---

## 三、Agent 设计与工具调用

### Q5: 你用了 4 个 Agent，为什么这样拆分？能不能合并成一个？

**A:** 拆分为 4 个专门化 Agent 的考虑：

1. **关注点分离**: 每个 Agent 有独立的 system prompt 和职责，更容易调试和优化
2. **工具隔离**: Planner Agent 不需要外部工具（只整合已有数据），其他 Agent 不需要行程规划能力
3. **错误隔离**: 某个 Agent 失败不影响其他 Agent 执行（通过条件错误路由）
4. **可扩展性**: 未来加一个"餐厅推荐 Agent"只需添加新节点

**能不能合并？** 可以。一个通用 Agent 配上所有工具和一段很长的 prompt 理论上也能完成任务。但会有以下问题：
- Prompt 太长容易丢失指令（context window 有限）
- 一次性调用多个工具容易遗漏
- 无法在中途检查中间结果（比如天气查到了但景点没找到）
- 调试困难，不知道哪个环节出了问题

不过，单 Agent 方案也有优势（减少 LLM 调用次数、降低成本、减少延迟），所以在实际产品中需要根据场景权衡。

### Q6: Agent 是怎么创建的？`langchain.agents.create_agent` 的工作原理是什么？

**A:** 使用 LangChain 的 `create_agent` API：
```python
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
)
```

`create_agent` 内部创建了一个 **ReAct 风格的 Agent 图**：
1. LLM 接收用户输入 + system prompt + 工具定义
2. LLM 决定调用哪个工具，输出 tool call
3. Agent 图执行工具，把结果返回给 LLM
4. LLM 基于工具结果决定下一步（继续调用工具或生成最终回答）
5. 循环直到 LLM 认为任务完成

每个 Agent 传入不同的 system prompt，规定了各自的职责和输出格式要求。

### Q7: Agent 怎么保证输出结构化的 JSON？

**A:** 采用了 **多层保障**：

1. **System Prompt 约束**: 在 prompt 中明确指定 JSON schema 示例，告诉 LLM 必须返回特定格式
2. **JSON 提取器**: `_extract_json()` 方法从 LLM 输出中抽取 JSON：
   - 先尝试 ````json ... ``` 代码块
   - 再尝试 ``` ... ``` 代码块
   - 再尝试 `[...]` 数组
   - 最后尝试 `{...}` 对象
3. **Pydantic 校验**: 提取后的 JSON 用 `json.loads()` 解析，再构造 Pydantic 模型（`TripPlan`、`Attraction` 等），校验失败会触发 fallback 计划
4. **Fallback 机制**: 如果解析完全失败，`_create_fallback_plan()` 生成一个基础行程

**不足**：当前方案依赖 prompt 工程，不如 LangChain 的 `StructuredOutputParser` 或 OpenAI 的 `response_format` 参数可靠，这是可以改进的地方。

### Q8: 工具调用的异步/同步是怎么处理的？

**A:** MCP 工具通常是异步的（只实现了 `_arun`），但 LangGraph 工具节点需要同步调用。我写了 `wrap_async_tools()` 包装器：

```python
def wrap_async_tools(tools):
    for tool in tools:
        if has_arun and not has_run:
            class SyncWrapper(tool.__class__):
                def _run(self, *args, **kwargs):
                    return _run_async(self._arun(*args, **kwargs))
```

`_run_async()` 内部逻辑：
1. 先尝试 `asyncio.get_running_loop()` 检测是否有运行中的事件循环
2. 没有 → 直接用 `asyncio.run()` 执行
3. 有 → 用 `ThreadPoolExecutor` 在线程池中运行 `asyncio.run()`，避免阻塞

这是一个常见的 Python async/sync 桥接模式。

---

## 四、MCP（Model Context Protocol）

### Q9: 什么是 MCP？你的项目是怎么使用 MCP 的？

**A:** MCP（Model Context Protocol）是 Anthropic 提出的开放协议，用于标准化 AI 模型与外部数据源/工具之间的交互。核心思想：

- **MCP Server**: 暴露一组工具（tools）和资源（resources）
- **MCP Client**: 连接到 server，发现可用的工具，然后调用
- **传输层**: 支持 stdio（进程间通信）和 HTTP（远程调用）

在本项目中：
- 使用第三方 `amap-mcp-server`（将高德地图 API 封装为 MCP 服务）
- 通过 `langchain-mcp-adapters` 的 `load_mcp_tools()` 连接到 MCP server
- 传输方式为 **stdio**：启动 `uvx amap-mcp-server` 子进程，通过标准输入/输出通信
- 加载的工具（如 `maps_text_search`、`maps_weather`）被包装为 LangChain `BaseTool`，供 Agent 使用

```python
connection = {
    "command": "uvx",
    "args": ["amap-mcp-server"],
    "transport": "stdio",
    "env": {"AMAP_MAPS_API_KEY": settings.amap_api_key}
}
tools = await load_mcp_tools(session=None, connection=connection, ...)
```

### Q10: 如果 MCP Server 不可用怎么办？

**A:** 设计了**三级降级策略**：

1. **一级**: 正常加载所有 MCP 工具（`get_amap_mcp_tools()`）
2. **二级**: 如果加载失败，尝试只加载核心工具（`get_amap_essential_tools()`，只加载搜索和天气）
3. **三级**: 如果仍然失败，使用模拟工具（`create_mock_tools()`），返回硬编码的假数据

`get_cached_amap_tools()` 按这个优先级链依次尝试，确保开发环境下即使没有 API Key 也能运行。

### Q11: MCP 和其他工具调用方式（如 LangChain 原生 Tool、OpenAI Function Calling）有什么区别？

**A:**

| 维度 | MCP | LangChain Tool | OpenAI Function Calling |
|------|-----|----------------|------------------------|
| 标准化 | 开放协议，跨平台 | LangChain 生态内 | OpenAI 专用 |
| 传输方式 | stdio / HTTP | 直接 Python 调用 | HTTP（OpenAI API） |
| 工具定义 | JSON Schema 自动发现 | 手动 Python 定义 | OpenAI API schema |
| 多模型兼容 | 是（任何 MCP Client） | 是 | 仅 OpenAI |
| 部署模式 | 独立进程/服务 | 应用内 | 云端 |

MCP 的最大优势是 **工具提供方和消费方解耦**——高德地图的团队维护 MCP Server，我用任何语言的 MCP Client 都能调用。而 LangChain Tool 需要我在代码里手动实现每个工具。

---

## 五、状态管理与数据流

### Q12: 从前端到后端再到 Agent，一个请求的完整数据流是什么？

**A:**

```
1. 用户在 Home.vue 填写表单 → 点击"生成旅行计划"
2. 前端 axios POST /api/trip/plan（JSON body: TripRequest）
3. FastAPI 路由 trip.py 接收请求，调用 workflow.plan_trip(request)
4. TripPlannerWorkflow.plan_trip():
   a. 创建初始状态 create_initial_state(request)
   b. self.graph.invoke(initial_state) → 执行 LangGraph StateGraph
5. StateGraph 依次执行:
   a. search_attractions → Agent 调用 maps_text_search → 解析 JSON → 写入 state["attractions"]
   b. check_weather → Agent 调用 maps_weather → 解析 JSON → 写入 state["weather_info"]
   c. find_hotels → Agent 调用 maps_text_search(酒店关键词) → 写入 state["hotels"]
   d. plan_itinerary → Agent 整合所有数据 → 返回 JSON → 解析为 TripPlan
6. 最终状态中的 trip_plan 被返回给 FastAPI 路由
7. 路由包装为 TripPlanResponse，JSON 返回给前端
8. 前端存入 sessionStorage，跳转到 /result 页面渲染
```

整个链路中，LLM 被调用了 **4 次**（每个 Agent 各一次），每次 LLM 可能还会多次调用 MCP 工具。

### Q13: 各个 Agent 之间的数据是怎么流转的？planner agent 怎么知道前面 Agent 的结果？

**A:** 当前设计中，planner agent **不是直接读取 State 中的结构化数据**，而是通过 `_build_planner_query()` 方法构造一个包含所有中间结果摘要的自然语言 prompt：

```python
query = f"""请根据以下信息生成旅行计划:
**景点信息:** 已找到 {len(attractions)} 个景点，包括: {景点名列表}
**天气信息:** {len(weather)} 天天气预报
**酒店信息:** 已找到 {len(hotels)} 个酒店，包括: {酒店名列表}
"""
```

**这是一个可以改进的地方**。当前方案只传递了摘要信息（数量、名称），没有传递完整的结构化数据（经纬度、价格、评分等），导致 planner agent 可能编造数据。更好的做法是把完整的 JSON 数据注入到 prompt 中。

---

## 六、错误处理与可靠性

### Q14: 如果某个 Agent 调用失败了，系统怎么处理？

**A:** 两层错误处理：

1. **节点级别**: 每个节点函数有 `try/except`，捕获异常后返回 `{"error": "...", "current_step": "error"}`
2. **图级别**: `add_conditional_edges` 的 `_check_error` 函数检测 `state["error"]`：
   - 如果存在 → 路由到 `handle_error` 节点
   - `handle_error` 调用 `_create_fallback_plan()` 生成一个基础行程

这样即使所有 Agent 都失败，用户也能拿到一个基础的（虽然不够精准的）旅行计划，而不是一个 500 错误。

### Q15: LLM 输出不稳定怎么办？比如 JSON 格式不对、数据有缺失？

**A:** 当前采取了以下措施：

1. **JSON 提取容错**: `_extract_json()` 支持多种格式（markdown code block、直接 JSON 对象/数组）
2. **Pydantic 校验**: 解析后的 JSON 用 Pydantic 模型校验，自动检测字段缺失/类型错误
3. **Fallback 计划**: 解析失败时 `_create_fallback_plan()` 返回基础行程
4. **温度设置**: `temperature=0.7`，在保证创造性的同时不至于太随机

**可以改进的方向**：
- 使用 OpenAI 的 `response_format={"type": "json_object"}` 强制 JSON 输出
- 使用 LangChain 的 `with_structured_output()` 自动将 LLM 输出映射为 Pydantic 模型
- 增加重试机制（解析失败后让 LLM 重新生成）

---

## 七、LLM 集成

### Q16: 为什么选择 qwen3.5-flash？和其他模型对比过吗？

**A:** 选择 qwen3.5-flash 的原因：
1. **中文能力强**: 通义千问对中文理解和生成质量优秀，旅行规划场景涉及大量中文 POI 名称和地址
2. **成本低**: flash 版本相比 plus/max 模型成本显著更低
3. **速度**: 推理速度快，用户体验好（整个工作流涉及 4 次 LLM 调用，速度很重要）
4. **OpenAI 兼容**: Dashscope 提供 OpenAI 兼容端点，可以直接用 `langchain-openai` 的 `ChatOpenAI` 接入，无需额外适配

如果要追求更高精度，可以考虑 qwen-plus 或 qwen-max，但成本和延迟会增加。

### Q17: 一次旅行规划要调用多少次 LLM？延迟和成本大概是多少？

**A:** 每次旅行规划至少调用 **4 次 LLM**（每个 Agent 一次），每个 Agent 内部还可能触发多轮 tool call（LLM → tool → LLM 循环）。

假设每个 Agent 平均 2 轮 tool call，那么总共约 **8-12 次 LLM API 调用**。

估算（以 qwen3.5-flash 计）：
- 每次调用平均 2K tokens 输入 + 1K tokens 输出 = 3K tokens
- 8-12 次 ≈ 24K-36K tokens ≈ 几毛钱人民币

**优化方向**：
- 合并 Agent（减少 LLM 调用次数）
- 工具结果缓存（同样的城市+关键词不重复搜索）
- 流式输出（让用户提前看到部分结果）

---

## 八、系统设计 & 扩展

### Q18: 如果让你重新设计这个系统，你会做哪些改进？

**A:** 这是我认为当前项目最需要改进的几点：

**1. Agent 间数据传递方式**
当前 planner agent 只收到摘要文本，应该改为传递完整的结构化数据（JSON），让 LLM 基于真实数据规划，而不是编造。

**2. 工作流拓扑**
当前是线性流水线，可以改为 DAG 或并行：景点搜索和天气查询之间没有依赖关系，可以并行执行，减少总延迟。

```
ENTRY → search_attractions ──┐
                              ├──→ plan_itinerary → END
ENTRY → check_weather ────────┘
```

**3. 结构化输出**
用 `with_structured_output()` 替代手动 JSON 提取，让框架自动完成 JSON schema → LLM output → Pydantic 的映射。

**4. Checkpoint & 持久化**
引入 LangGraph 的 `checkpointer`（如 `SqliteSaver`），支持中断恢复。这样如果用户在生成过程中关闭页面，下次可以从中断点继续。

**5. 测试覆盖**
当前没有测试。应该补充：
- Agent prompt 的单元测试（验证输出格式）
- JSON 解析器的边界测试
- MCP 工具 mock 测试

**6. 流式响应**
改为 SSE（Server-Sent Events）流式返回，让用户实时看到工作流进度（"正在搜索景点..." → "已找到 5 个景点" → "正在查询天气..."）。

### Q19: 如果并发量很大，系统瓶颈在哪里？怎么优化？

**A:** 主要瓶颈：

1. **LLM API 调用**: 串行 4 次 LLM 调用是最大的延迟来源
   - 优化：并行化无依赖的 Agent（景点 + 天气）、结果缓存

2. **MCP Server 进程**: stdio 传输意味着每个请求启动一个新进程
   - 优化：MCP Server 常驻进程 + HTTP 传输，或工具调用直接调 HTTP API

3. **单例模式**: `_trip_planner_workflow` 全局单例，所有请求共享
   - 优化：工具可以共享，但每次请求应有独立的状态实例

4. **LLM 温度 + 重试**: temperature=0.7 可能导致偶尔需要重试
   - 优化：降低温度 + 显式重试逻辑

### Q20: 这个项目中你觉得最有技术挑战的部分是什么？

**A:** 我认为是 **MCP 工具的异步/同步桥接** 和 **LangGraph 状态管理**：

1. **MCP 工具桥接**: `langchain-mcp-adapters` 返回的工具只实现了异步方法（`_arun`），但 LangGraph 的工具节点需要同步调用（`_run`）。需要正确处理 Python 事件循环的冲突——当 FastAPI 已经在 asyncio 事件中运行时，不能直接 `asyncio.run()`，必须用线程池。这个问题调试了很久，最终通过检测运行中事件循环 + 线程池方案解决。

2. **LangGraph 状态管理**: 理解 `Annotated` reducer 的工作机制、节点返回值如何合并到全局状态、条件边如何路由——这些概念和传统的函数式编程不太一样。特别是调试时，因为 LangGraph 内部有很多隐式行为，需要深入理解其执行模型。

---

## 九、前端相关

### Q21: 前端是怎么和后端交互的？地图是怎么展示的？

**A:** 
- **API 交互**: 通过 Axios 封装的 `api.ts`，调用 `POST /api/trip/plan`，设置超时约 5.8 分钟（因为 LLM 调用链可能较长）
- **Vite 代理**: `vite.config.ts` 配置了 `/api` → `http://localhost:8000` 的代理，解决开发环境跨域
- **地图展示**: 使用 `@amap/amap-jsapi-loader` 加载高德地图 JS API，在 `Result.vue` 中：
  - 根据行程中的景点经纬度创建 `AMap.Marker`
  - 绘制景点之间的路线（`AMap.Polyline`）
  - 支持编辑模式（拖拽排序、删除景点）
- **导出功能**: 用 `html2canvas` 截图 + `jspdf` 生成 PDF

### Q22: 前后端的数据类型是怎么对齐的？

**A:** 后端用 Pydantic 模型（`TripPlan`、`DayPlan`、`Attraction` 等），前端用对应的 TypeScript 接口（`types/index.ts`）。字段名保持一致，Pydantic 序列化后的 JSON 可以直接被 TypeScript 类型消费。温度字段在后端用了 `field_validator` 移除 `°C` 等单位符号，前端直接当数字处理。

---

## 十、项目反思 & 自我评价

### Q23: 你觉得这个项目的亮点是什么？

**A:**
1. **完整的多 Agent 架构**: 不是简单的单 Agent + 工具，而是用 LangGraph 编排了多个专门化 Agent，展示了真正的 multi-agent orchestration 能力
2. **MCP 协议集成**: 接入了高德地图 MCP 服务，获取真实的 POI、天气数据，而不是硬编数据
3. **端到端完整**: 从前端表单 → FastAPI → LangGraph → Agent → MCP → LLM → 前端地图渲染，全链路打通
4. **容错设计**: 三级工具降级 + 节点级异常处理 + fallback 计划，保证系统可用性

### Q24: 如果给你更多时间，你会优先做什么？

**A:**
1. **结构化输出改造**: 用 `with_structured_output()` 替换手动 JSON 提取，提高输出可靠性
2. **并行化工作流**: 让无依赖的 Agent 并行执行，减少端到端延迟
3. **流式输出**: SSE 实时展示工作流进度，提升用户体验
4. **LangSmith 集成**: 启用 LangSmith tracing，可视化 Agent 执行过程，方便调试和评估
5. **测试覆盖**: 补充单元测试和集成测试
6. **完整的数据传递**: 让 planner agent 接收完整的结构化中间数据而非摘要

### Q25: 你在做这个项目的过程中学到了什么？

**A:**
1. **LangGraph 的状态图模型**: 理解了 StateGraph、reducer、条件边、checkpoint 等概念，以及它和传统 Chain 的区别
2. **MCP 协议的实践**: 不仅理解了 MCP 的协议规范，还实际处理了 stdio 传输、异步桥接、降级策略等工程问题
3. **Prompt 工程的边界**: 意识到纯靠 prompt 约束 JSON 格式的脆弱性，理解了为什么需要 structured output 方案
4. **Python async 编程**: 深入理解了 asyncio 事件循环、`asyncio.run()` 的限制、ThreadPoolExecutor 桥接等
5. **端到端系统思维**: 从 LLM 调用到前端渲染，每一层都可能出问题，需要全链路的容错和可观测性设计

---

## 附录：可能被深挖的技术点速查

### LangGraph 相关
- `StateGraph` vs `MessageGraph` vs `CompiledGraph` 的区别
- `checkpointer`（MemorySaver / SqliteSaver）的使用场景
- `interrupt_before` / `interrupt_after` 人机交互
- `subgraph` 嵌套工作流

### MCP 相关
- MCP 协议的三种传输：stdio、HTTP SSE、HTTP Stream
- MCP Server 的 tools / resources / prompts 三个能力
- `amap-mcp-server` 的源码结构（如何把高德 REST API 映射为 MCP tools）

### LLM 相关
- Tool Calling / Function Calling 的原理
- ReAct pattern（Reasoning + Acting）
- `with_structured_output()` vs 手动 JSON 解析
- 上下文窗口限制和长 prompt 处理

### FastAPI 相关
- Pydantic v2 的 `field_validator` vs v1 的 `validator`
- CORS 中间件配置
- 依赖注入（`Depends`）
- 异步路由 vs 同步路由
