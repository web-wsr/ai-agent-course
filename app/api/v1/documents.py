import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.dependencies.redis import get_redis_client
from app.redis.document_state import get_document_parse_state, set_document_parse_state
from app.schemas.response import ApiResponse
from app.services.document_service import parse_document

router = APIRouter()


class DocumentParseRequest(BaseModel):
    document_id: str = Field(..., min_length=1, description="文档 ID")
    simulate_failure: bool = Field(default=False, description="是否模拟解析失败")


@router.post(
    "/documents/parse",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_document_parse_task(
    request: DocumentParseRequest,
    background_tasks: BackgroundTasks,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> ApiResponse[dict]:
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    state = {
        "task_id": task_id,
        "document_id": request.document_id,
        "status": "pending",
    }
    await set_document_parse_state(redis=redis, task_id=task_id, state=state)
    background_tasks.add_task(
        parse_document,
        redis=redis,
        task_id=task_id,
        document_id=request.document_id,
        simulate_failure=request.simulate_failure,
    )
    return ApiResponse[dict](data=state)


@router.get("/documents/tasks/{task_id}", response_model=ApiResponse[dict])
async def get_document_parse_task(
    task_id: str,
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> ApiResponse[dict]:
    state = await get_document_parse_state(redis=redis, task_id=task_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档解析任务不存在或已过期",
        )
    return ApiResponse[dict](data=state)
