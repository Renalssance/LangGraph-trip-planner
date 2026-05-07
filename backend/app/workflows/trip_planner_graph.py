"""旅行规划 LangGraph 工作流"""

from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from .trip_planner_state import TripPlannerState, create_initial_state, has_error
from ..agents.langgraph_agents import (
    create_attraction_search_agent,
    create_weather_agent,
    create_hotel_agent,
    create_planner_agent
)
from ..agents.evaluator_agent import evaluate_plan
from ..agents.reviser_agent import revise_plan
from ..evals import should_revise_plan
from ..tools.amap_mcp_tools import get_cached_amap_tools
from ..rag import TravelKnowledgeRetriever
from ..skills import estimate_budget, extract_json, generate_trip_report
from ..models.schemas import (
    TripRequest, TripPlan, DayPlan, Attraction, Meal, WeatherInfo,
    Location, Hotel, Budget
)

# 设置日志记录
logger = logging.getLogger(__name__)


class TripPlannerWorkflow:
    """多智能体旅行规划工作流 (LangGraph 版本)"""

    def __init__(self):
        """初始化工作流"""
        logger.info("🔄 初始化 LangGraph 旅行规划工作流...")

        try:
            # 初始化工具
            self.tools = get_cached_amap_tools()
            if not self.tools:
                logger.warning("⚠️  未加载到任何工具，工作流可能无法正常工作")
            else:
                logger.info(f"✅ 加载了 {len(self.tools)} 个工具")
                for tool in self.tools:
                    logger.debug(f"  工具: {tool.name} - {tool.description}")

            # 创建智能体
            logger.info("创建智能体...")
            self.attraction_agent = create_attraction_search_agent(self.tools)
            self.weather_agent = create_weather_agent(self.tools)
            self.hotel_agent = create_hotel_agent(self.tools)
            self.planner_agent = create_planner_agent([])  # 行程规划不需要外部工具
            self.knowledge_retriever = TravelKnowledgeRetriever()

            # 构建工作流图
            logger.info("构建 StateGraph...")
            self.graph = self._build_graph()

            logger.info("✅ LangGraph 工作流初始化成功")

        except Exception as e:
            logger.error(f"❌ 工作流初始化失败: {str(e)}", exc_info=True)
            raise

    def _prepare_agent_input(self, user_input: str, chat_history: list) -> dict:
        """准备智能体输入格式，将 input 和 chat_history 转换为 messages 格式"""
        messages = []
        # 添加历史消息（如果存在）
        for msg in chat_history:
            # 假设历史消息格式为 {"role": "...", "content": "..."}
            messages.append(msg)
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        return {"messages": messages}

    def _extract_agent_output(self, result: dict) -> str:
        """从智能体结果中提取输出文本

        新的 create_agent API 返回的结果包含 'messages' 列表，
        需要提取最后一个 assistant 消息的内容。
        """
        if "messages" in result:
            messages = result["messages"]
            # 查找最后一个 assistant 消息
            for msg in reversed(messages):
                # 处理字典格式的消息
                if isinstance(msg, dict):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        # 如果 content 是字典，转换为字符串
                        if isinstance(content, dict):
                            import json
                            content = json.dumps(content, ensure_ascii=False)
                        return str(content)
                else:
                    # 处理 LangChain 消息对象 (AIMessage, HumanMessage 等)
                    # 尝试获取消息类型
                    msg_type = None
                    if hasattr(msg, 'type'):
                        msg_type = msg.type
                    elif hasattr(msg, 'role'):
                        msg_type = msg.role

                    # 检查是否是 assistant/ai 消息
                    if msg_type in ["assistant", "ai"]:
                        content = ""
                        if hasattr(msg, 'content'):
                            content = msg.content
                        elif hasattr(msg, 'get'):
                            content = msg.get("content", "")
                        # 如果 content 是字典，转换为字符串
                        if isinstance(content, dict):
                            import json
                            content = json.dumps(content, ensure_ascii=False)
                        return str(content)
            # 如果没有找到 assistant 消息，返回空字符串
            return ""
        elif "output" in result:
            # 兼容旧格式
            return result["output"]
        else:
            # 尝试查找其他可能的字段
            for key in ["text", "response", "content"]:
                if key in result:
                    return str(result[key])
            # 如果都没有，返回整个结果的字符串表示
            return str(result)

    def _build_graph(self) -> StateGraph:
        """构建 StateGraph"""
        workflow = StateGraph(TripPlannerState)
        # 添加节点
        workflow.add_node("retrieve_knowledge", self._retrieve_knowledge)
        workflow.add_node("search_attractions", self._search_attractions)
        workflow.add_node("check_weather", self._check_weather)
        workflow.add_node("find_hotels", self._find_hotels)
        workflow.add_node("plan_itinerary", self._plan_itinerary)
        workflow.add_node("evaluate_plan", self._evaluate_plan)
        workflow.add_node("revise_plan", self._revise_plan)
        workflow.add_node("handle_error", self._handle_error)
        # 设置入口点
        workflow.set_entry_point("retrieve_knowledge")
        # 添加边（正常流程）
        workflow.add_edge("plan_itinerary", "evaluate_plan")
        # 添加错误处理边
        workflow.add_conditional_edges(
            "retrieve_knowledge",
            self._check_error,
            {
                "continue": "search_attractions",
                "error": "handle_error"
            }
        )

        workflow.add_conditional_edges(
            "search_attractions",
            self._check_error,
            {
                "continue": "check_weather",
                "error": "handle_error"
            }
        )

        workflow.add_conditional_edges(
            "check_weather",
            self._check_error,
            {
                "continue": "find_hotels",
                "error": "handle_error"
            }
        )

        workflow.add_conditional_edges(
            "find_hotels",
            self._check_error,
            {
                "continue": "plan_itinerary",
                "error": "handle_error"
            }
        )

        workflow.add_conditional_edges(
            "evaluate_plan",
            self._should_revise,
            {
                "revise": "revise_plan",
                "finish": END,
            }
        )
        workflow.add_edge("revise_plan", "evaluate_plan")
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _retrieve_knowledge(self, state: TripPlannerState) -> Dict[str, Any]:
        """检索目的地知识和用户偏好上下文节点"""
        logger.info("📚 检索旅行知识...")
        try:
            context = self.knowledge_retriever.retrieve_for_request(state["request"])
            doc_count = (
                len(context["retrieved_city_docs"])
                + len(context["retrieved_attraction_docs"])
                + len(context["user_profile_context"].get("retrieved_docs", []))
            )
            return {
                **context,
                "current_step": "knowledge_retrieved",
                "messages": [{"role": "assistant", "content": f"已检索 {doc_count} 条旅行知识"}],
            }
        except Exception as e:
            logger.error(f"旅行知识检索失败: {str(e)}", exc_info=True)
            return {
                "error": f"旅行知识检索失败: {str(e)}",
                "current_step": "error",
            }

    def _search_attractions(self, state: TripPlannerState) -> Dict[str, Any]:
        """搜索景点节点"""
        logger.info("📍 搜索景点...")
        try:
            # 构建查询
            query = self._build_attraction_query(state["request"])
            if state.get("retrieved_attraction_docs"):
                docs = self._format_knowledge_docs(state["retrieved_attraction_docs"])
                query += f"\n\n可参考的景点知识:\n{docs}"

            # 执行智能体
            result = self.attraction_agent.invoke(
                self._prepare_agent_input(query, [])
            )

            # 更新状态
            output = self._extract_agent_output(result)
            attractions = self._parse_attractions(output)

            return {
                "attractions": attractions,
                "messages": [{"role": "assistant", "content": f"已找到 {len(attractions)} 个景点"}]
            }

        except Exception as e:
            logger.error(f"景点搜索失败: {str(e)}", exc_info=True)
            return {
                "error": f"景点搜索失败: {str(e)}",
                "current_step": "error"
            }

    def _check_weather(self, state: TripPlannerState) -> Dict[str, Any]:
        """查询天气节点"""
        logger.info("🌤️  查询天气...")
        try:
            query = f"查询{state['request'].city}的天气信息"

            result = self.weather_agent.invoke(
                self._prepare_agent_input(query, [])
            )

            output = self._extract_agent_output(result)
            weather_info = self._parse_weather(output)

            return {
                "weather_info": weather_info,
                "messages": [{"role": "assistant", "content": f"已获取 {len(weather_info)} 天天气信息"}]
            }

        except Exception as e:
            logger.error(f"天气查询失败: {str(e)}", exc_info=True)
            return {
                "error": f"天气查询失败: {str(e)}",
                "current_step": "error"
            }

    def _find_hotels(self, state: TripPlannerState) -> Dict[str, Any]:
        """搜索酒店节点"""
        logger.info("🏨 搜索酒店...")
        try:
            query = f"搜索{state['request'].city}的{state['request'].accommodation}酒店"

            result = self.hotel_agent.invoke(
                self._prepare_agent_input(query, [])
            )

            output = self._extract_agent_output(result)
            hotels = self._parse_hotels(output)

            return {
                "hotels": hotels,
                "current_step": "hotels_found",
                "messages": [{"role": "assistant", "content": f"已找到 {len(hotels)} 个酒店"}]
            }

        except Exception as e:
            logger.error(f"酒店搜索失败: {str(e)}", exc_info=True)
            return {
                "error": f"酒店搜索失败: {str(e)}",
                "current_step": "error"
            }

    def _plan_itinerary(self, state: TripPlannerState) -> Dict[str, Any]:
        """生成行程计划节点"""
        logger.info("📋 生成行程计划...")
        try:
            # 构建规划查询
            query = self._build_planner_query(
                state["request"],
                state["attractions"],
                state["weather_info"],
                state["hotels"],
                state.get("retrieved_city_docs", []),
                state.get("retrieved_attraction_docs", []),
                state.get("user_profile_context", {})
            )

            result = self.planner_agent.invoke(
                self._prepare_agent_input(query, [])
            )

            output = self._extract_agent_output(result)
            trip_plan = self._parse_trip_plan(output, state["request"])
            trip_plan = self._apply_plan_skills(trip_plan, state["request"])
            report = generate_trip_report(trip_plan)

            return {
                "draft_plan": trip_plan,
                "trip_plan": trip_plan,
                "final_report": report,
                "current_step": "plan_completed",
                "messages": [{"role": "assistant", "content": "行程计划生成完成！"}]
            }

        except Exception as e:
            logger.error(f"行程规划失败: {str(e)}", exc_info=True)
            return {
                "error": f"行程规划失败: {str(e)}",
                "current_step": "error"
            }

    def _handle_error(self, state: TripPlannerState) -> Dict[str, Any]:
        """错误处理节点"""
        error_msg = state.get('error', '未知错误')
        logger.warning(f"⚠️  处理错误: {error_msg}")

        # 创建备用计划
        fallback_plan = self._create_fallback_plan(state["request"])
        report = generate_trip_report(fallback_plan)

        return {
            "trip_plan": fallback_plan,
            "draft_plan": fallback_plan,
            "final_report": report,
            "current_step": "error_handled",
            "messages": [{"role": "assistant", "content": f"遇到错误，已生成备用计划: {error_msg}"}]
        }

    def _check_error(self, state: TripPlannerState) -> str:
        """检查是否有错误"""
        return "error" if state.get("error") else "continue"

    def _evaluate_plan(self, state: TripPlannerState) -> Dict[str, Any]:
        """评估当前行程计划节点"""
        logger.info("🧪 评估行程质量...")
        try:
            plan = state.get("trip_plan") or state.get("draft_plan")
            if not plan:
                return {
                    "error": "评估失败: 缺少行程计划",
                    "current_step": "error",
                }

            evaluation_result = evaluate_plan(plan, state["request"])
            return {
                "evaluation_result": evaluation_result,
                "current_step": "plan_evaluated",
                "messages": [
                    {
                        "role": "assistant",
                        "content": f"行程评估完成，得分 {evaluation_result['total_score']}",
                    }
                ],
            }
        except Exception as e:
            logger.error(f"行程评估失败: {str(e)}", exc_info=True)
            return {
                "error": f"行程评估失败: {str(e)}",
                "current_step": "error",
            }

    def _revise_plan(self, state: TripPlannerState) -> Dict[str, Any]:
        """根据评估结果修正行程计划节点"""
        logger.info("🛠️  修正行程计划...")
        try:
            plan = state.get("trip_plan") or state.get("draft_plan")
            if not plan:
                return {
                    "error": "修正失败: 缺少行程计划",
                    "current_step": "error",
                }

            revised_plan = revise_plan(plan, state["request"], state.get("evaluation_result", {}))
            report = generate_trip_report(revised_plan)
            revision_count = state.get("revision_count", 0) + 1
            return {
                "trip_plan": revised_plan,
                "draft_plan": revised_plan,
                "final_report": report,
                "revision_count": revision_count,
                "current_step": "plan_revised",
                "messages": [{"role": "assistant", "content": f"已完成第 {revision_count} 轮行程修正"}],
            }
        except Exception as e:
            logger.error(f"行程修正失败: {str(e)}", exc_info=True)
            return {
                "error": f"行程修正失败: {str(e)}",
                "current_step": "error",
            }

    def _should_revise(self, state: TripPlannerState) -> str:
        """根据评估结果和修正次数决定是否继续修正。"""
        if state.get("error"):
            return "finish"
        if should_revise_plan(state.get("evaluation_result", {}), state.get("revision_count", 0)):
            return "revise"
        return "finish"

    # ============ 辅助方法（从原 trip_planner_agent.py 迁移）============

    def _build_attraction_query(self, request: TripRequest) -> str:
        """构建景点搜索查询"""
        if request.preferences:
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        return f"请搜索{request.city}的{keywords}相关景点"

    def _build_planner_query(
        self,
        request: TripRequest,
        attractions: List[Attraction],
        weather: List[WeatherInfo],
        hotels: List[Hotel],
        city_docs: List[Dict[str, Any]] | None = None,
        attraction_docs: List[Dict[str, Any]] | None = None,
        user_profile_context: Dict[str, Any] | None = None,
    ) -> str:
        """构建行程规划查询"""
        city_context = self._format_knowledge_docs(city_docs or [])
        attraction_context = self._format_knowledge_docs(attraction_docs or [])
        preference_context = self._format_user_profile_context(user_profile_context or {})
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
已找到 {len(attractions)} 个景点，包括：{', '.join([a.name for a in attractions[:3]]) if attractions else '无'}

**天气信息:**
{len(weather)} 天天气预报

**酒店信息:**
已找到 {len(hotels)} 个酒店，包括：{', '.join([h.name for h in hotels[:2]]) if hotels else '无'}

**RAG检索到的城市和通用旅行知识:**
{city_context or '无'}

**RAG检索到的景点知识:**
{attraction_context or '无'}

**用户偏好上下文:**
{preference_context or '无'}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
4. 考虑景点之间的距离和交通方式
5. 返回完整的JSON格式数据
6. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query

    def _format_knowledge_docs(self, docs: List[Dict[str, Any]]) -> str:
        """格式化 RAG 文档，作为 agent 输入上下文。"""
        lines = []
        for index, doc in enumerate(docs[:6], start=1):
            title = doc.get("title", "未命名知识")
            content = doc.get("content", "")
            tags = ", ".join(doc.get("tags", []))
            suffix = f" 标签: {tags}" if tags else ""
            lines.append(f"{index}. {title}: {content}{suffix}")
        return "\n".join(lines)

    def _format_user_profile_context(self, context: Dict[str, Any]) -> str:
        """格式化用户偏好和历史偏好知识。"""
        parts = []
        preferences = context.get("preferences") or []
        if preferences:
            parts.append(f"显式偏好: {', '.join(preferences)}")
        if context.get("free_text_input"):
            parts.append(f"补充要求: {context['free_text_input']}")
        docs = context.get("retrieved_docs") or []
        if docs:
            parts.append("偏好知识:\n" + self._format_knowledge_docs(docs))
        return "\n".join(parts)

    def _extract_json(self, response: str) -> str:
        """从响应文本中提取JSON字符串"""
        return extract_json(response)

    def _apply_plan_skills(self, trip_plan: TripPlan, request: TripRequest) -> TripPlan:
        """应用可复用 Skills 补强行程结构。"""
        if not trip_plan.budget or trip_plan.budget.total <= 0:
            trip_plan.budget = estimate_budget(trip_plan, request)
        return trip_plan

    def _parse_attractions(self, response: str) -> List[Attraction]:
        """解析景点信息"""
        try:
            # 尝试从响应中提取JSON
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            # 假设数据是景点列表
            attractions = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # 转换为Attraction对象
                        attraction = Attraction(
                            name=item.get("name", ""),
                            address=item.get("address", ""),
                            location=Location(
                                longitude=item.get("location", {}).get("longitude", 0.0),
                                latitude=item.get("location", {}).get("latitude", 0.0)
                            ),
                            visit_duration=item.get("visit_duration", 120),
                            description=item.get("description", ""),
                            category=item.get("category", "景点"),
                            ticket_price=item.get("ticket_price", 0)
                        )
                        attractions.append(attraction)
            return attractions
        except Exception as e:
            logger.error(f"解析景点信息失败: {str(e)}")
            logger.error(f"原始响应长度: {len(response)}")
            logger.error(f"原始响应前500字符: {response[:500]}")
            logger.error(f"提取的JSON字符串长度: {len(json_str) if 'json_str' in locals() else 'N/A'}")
            if 'json_str' in locals():
                logger.error(f"提取的JSON字符串前500字符: {json_str[:500]}")
            # 返回空列表或示例数据
            return []

    def _parse_weather(self, response: str) -> List[WeatherInfo]:
        """解析天气信息"""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            weather_info = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        weather = WeatherInfo(
                            date=item.get("date", ""),
                            day_weather=item.get("day_weather", ""),
                            night_weather=item.get("night_weather", ""),
                            day_temp=item.get("day_temp", 0),
                            night_temp=item.get("night_temp", 0),
                            wind_direction=item.get("wind_direction", ""),
                            wind_power=item.get("wind_power", "")
                        )
                        weather_info.append(weather)
            return weather_info
        except Exception as e:
            logger.error(f"解析天气信息失败: {str(e)}")
            return []

    def _parse_hotels(self, response: str) -> List[Hotel]:
        """解析酒店信息"""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            hotels = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        hotel = Hotel(
                            name=item.get("name", ""),
                            address=item.get("address", ""),
                            location=Location(
                                longitude=item.get("location", {}).get("longitude", 0.0),
                                latitude=item.get("location", {}).get("latitude", 0.0)
                            ) if item.get("location") else None,
                            price_range=item.get("price_range", ""),
                            rating=item.get("rating", ""),
                            distance=item.get("distance", ""),
                            type=item.get("type", ""),
                            estimated_cost=item.get("estimated_cost", 0)
                        )
                        hotels.append(hotel)
            return hotels
        except Exception as e:
            logger.error(f"解析酒店信息失败: {str(e)}")
            return []

    def _parse_trip_plan(self, response: str, request: TripRequest) -> TripPlan:
        """解析行程计划"""
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)

            # 转换为TripPlan对象
            trip_plan = TripPlan(
                city=data.get("city", request.city),
                start_date=data.get("start_date", request.start_date),
                end_date=data.get("end_date", request.end_date),
                days=[],
                weather_info=[],
                overall_suggestions=data.get("overall_suggestions", ""),
                budget=None
            )

            # 解析天气信息
            for weather_data in data.get("weather_info", []):
                weather_info = WeatherInfo(**weather_data)
                trip_plan.weather_info.append(weather_info)

            # 解析每日行程
            for day_data in data.get("days", []):
                # 解析景点
                attractions = []
                for attr_data in day_data.get("attractions", []):
                    attraction = Attraction(**attr_data)
                    attractions.append(attraction)

                # 解析餐饮
                meals = []
                for meal_data in day_data.get("meals", []):
                    meal = Meal(**meal_data)
                    meals.append(meal)

                # 解析酒店
                hotel_data = day_data.get("hotel")
                hotel = Hotel(**hotel_data) if hotel_data else None

                day_plan = DayPlan(
                    date=day_data.get("date", ""),
                    day_index=day_data.get("day_index", 0),
                    description=day_data.get("description", ""),
                    transportation=day_data.get("transportation", request.transportation),
                    accommodation=day_data.get("accommodation", request.accommodation),
                    hotel=hotel,
                    attractions=attractions,
                    meals=meals
                )
                trip_plan.days.append(day_plan)

            # 解析预算
            budget_data = data.get("budget")
            if budget_data:
                budget = Budget(**budget_data)
                trip_plan.budget = budget

            return trip_plan
        except Exception as e:
            logger.error(f"解析行程计划失败: {str(e)}")
            # 返回备用计划
            return self._create_fallback_plan(request)

    def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
        """创建备用计划(当Agent失败时)"""
        # 解析日期
        try:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        except ValueError:
            # 如果日期格式错误，使用当前日期
            start_date = datetime.now()

        # 创建每日行程
        days = []
        for i in range(request.travel_days):
            current_date = start_date + timedelta(days=i)

            day_plan = DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i+1}天行程",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=[
                    Attraction(
                        name=f"{request.city}景点{j+1}",
                        address=f"{request.city}市",
                        location=Location(longitude=116.4 + i*0.01 + j*0.005, latitude=39.9 + i*0.01 + j*0.005),
                        visit_duration=120,
                        description=f"这是{request.city}的著名景点",
                        category="景点"
                    )
                    for j in range(2)
                ],
                meals=[
                    Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐"),
                    Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐"),
                    Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐")
                ]
            )
            days.append(day_plan)

        fallback_plan = TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=[],
            overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程,建议提前查看各景点的开放时间。"
        )
        return self._apply_plan_skills(fallback_plan, request)

    def plan_trip(self, request: TripRequest) -> TripPlan:
        """执行旅行规划工作流"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 开始 LangGraph 旅行规划工作流...")
        logger.info(f"目的地: {request.city}")
        logger.info(f"{'='*60}\n")

        # 初始化状态
        initial_state: TripPlannerState = create_initial_state(request)

        # 执行工作流
        final_state = self.graph.invoke(initial_state)

        # 检查结果
        if final_state.get("error") and not final_state.get("trip_plan"):
            error_msg = final_state.get("error", "未知错误")
            logger.error(f"❌ 旅行规划失败: {error_msg}")
            raise Exception(error_msg)

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ 旅行计划生成完成!")
        logger.info(f"{'='*60}\n")

        return final_state["trip_plan"]


# 全局工作流实例
_trip_planner_workflow: Optional[TripPlannerWorkflow] = None


def get_trip_planner_workflow() -> TripPlannerWorkflow:
    """获取旅行规划工作流实例（单例模式）"""
    global _trip_planner_workflow

    if _trip_planner_workflow is None:
        _trip_planner_workflow = TripPlannerWorkflow()

    return _trip_planner_workflow


def reset_workflow():
    """重置工作流实例（用于测试或重新配置）"""
    global _trip_planner_workflow
    _trip_planner_workflow = None
    logger.info("工作流实例已重置")
