"""旅行规划API路由 (LangGraph 版本)"""

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
import json
import logging
from ...models.schemas import (
    TripRequest,
    TripPlanResponse,
    ErrorResponse
)
# 从新的工作流导入
from ...workflows.trip_planner_graph import get_trip_planner_workflow

router = APIRouter(prefix="/trip", tags=["旅行规划"])
logger = logging.getLogger(__name__)


def _sse_event(payload: dict) -> str:
    """Serialize one Server-Sent Event data frame."""
    return f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(request: TripRequest):
    """
    生成旅行计划 (LangGraph 版本)

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"📥 收到旅行规划请求 (LangGraph):")
        logger.info(f"   城市: {request.city}")
        logger.info(f"   日期: {request.start_date} - {request.end_date}")
        logger.info(f"   天数: {request.travel_days}")
        logger.info(f"{'='*60}\n")

        # 获取工作流实例
        logger.info("🔄 获取 LangGraph 工作流实例...")
        workflow = get_trip_planner_workflow()

        # 执行工作流
        logger.info("🚀 开始执行工作流...")
        trip_plan = workflow.plan_trip(request)

        logger.info("✅ 旅行计划生成成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功 (LangGraph)",
            data=trip_plan
        )

    except Exception as e:
        logger.error(f"❌ 生成旅行计划失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.post(
    "/plan/stream",
    summary="流式生成旅行计划",
    description="根据真实 LangGraph 节点执行进度,持续返回旅行规划进度事件"
)
async def plan_trip_stream(request: TripRequest):
    """流式生成旅行计划进度和最终结果。"""

    def event_stream():
        try:
            logger.info(f"\n{'='*60}")
            logger.info("📥 收到旅行规划流式请求 (LangGraph):")
            logger.info(f"   城市: {request.city}")
            logger.info(f"   日期: {request.start_date} - {request.end_date}")
            logger.info(f"   天数: {request.travel_days}")
            logger.info(f"{'='*60}\n")

            yield _sse_event({
                "event": "progress",
                "step": "request_received",
                "title": "收到旅行规划请求",
                "detail": f"目的地 {request.city}，{request.travel_days} 天行程",
                "percent": 2,
                "status": "done",
            })
            yield _sse_event({
                "event": "progress",
                "step": "workflow_loading",
                "title": "获取 LangGraph 工作流实例",
                "detail": "正在准备工具、Agent 和旅行知识检索器",
                "percent": 5,
                "status": "active",
            })

            workflow = get_trip_planner_workflow()
            for progress_event in workflow.plan_trip_with_progress(request):
                yield _sse_event(progress_event)

        except Exception as e:
            logger.error(f"❌ 流式生成旅行计划失败: {str(e)}", exc_info=True)
            yield _sse_event({
                "event": "error",
                "step": "error",
                "title": "旅行规划失败",
                "detail": str(e),
                "percent": 100,
                "status": "error",
                "message": f"生成旅行计划失败: {str(e)}",
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        workflow = get_trip_planner_workflow()

        return {
            "status": "healthy",
            "service": "trip-planner-langgraph",
            "framework": "LangGraph",
            "graph_compiled": True,
            "tools_loaded": len(workflow.tools) if hasattr(workflow, 'tools') else 0
        }
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )
