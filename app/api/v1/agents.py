import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.dependencies.redis import get_redis_client
from app.redis.agent_state import (
    get_agent_run_state,
    set_agent_run_state
)

from app.dependencies.agent_context import get_agent_context, AgentContext

from app.schemas.agent import AgentListResponse
from app.schemas.response import ApiResponse
from app.services.agent_service import list_agent_service
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AgentRunRequest(BaseModel):
   question: str = Field(..., description="问题")
   agent_id: str = Field(default="agent_chat", description="Agent ID")

class AgentRunResponse(BaseModel):
   answer: str = Field(..., description="Agent 回答")
   trace_id: str = Field(..., description="链路追踪 ID")
   debug: bool = Field(default=False, description="是否开启调试模式")

@router.get("/agents", response_model=ApiResponse[AgentListResponse])
async def list_agents() -> ApiResponse[AgentListResponse]:
   result = await list_agent_service()
   return ApiResponse[AgentListResponse] (
        data=result
   )

@router.post("/agents/run", response_model=ApiResponse[AgentRunResponse])
async def run_agent(
   request : AgentRunRequest,
   context: AgentContext = Depends(get_agent_context),
) -> ApiResponse[AgentRunResponse]:
   
   logger.info(
      f"agent_run_start agent_id={request.agent_id}"
   )

   answer = (
      f"用户 {context.current_user.username} 调用了 {request.agent_id}"
      f"问题是：{request.question}"
   )

   logger.info(
      f"agent_run_success agent_id={request.agent_id}"
   )

   return ApiResponse[AgentRunResponse](
        data=AgentRunResponse(
            answer=answer,
            trace_id=context.trace_id,
            debug=context.debug
        )
   )




#创建任务，把状态写入 Redis
@router.post("/agents/run-async", response_model=ApiResponse[dict])
async def run_agent_async(
    request: AgentRunRequest,
    redis: Redis = Depends(get_redis_client),
    context: AgentContext = Depends(get_agent_context),
) -> ApiResponse[dict]:
    """
    异步运行代理
    """

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    await set_agent_run_state(
       redis=redis,
       run_id=run_id,
       state={
          "run_id": run_id,
          "agent_id": request.agent_id,
          "question": request.question,
          "status": "running",
          "current_step": "planning",
          "progress": 10,
          "trace_id": context.trace_id
       }
    )

    return ApiResponse[dict](
       data={
          "run_id": run_id,
          "status": "running",
          "trace_id": context.trace_id,
       }
    )
    

#查询任务状态。
@router.get("/agents/runs/{run_id}", response_model=ApiResponse[dict])
async def get_agent_run(
   run_id: str,
   redis: Redis = Depends(get_redis_client),
) -> ApiResponse[dict]:
    state = await get_agent_run_state(
       redis=redis,
       run_id=run_id
    )

    if not state:
       return ApiResponse[dict](
          code=40400,
          message="Agent Run 不存在或已过期",
          data=None
       )

    return ApiResponse[dict](
       data=state
    )