from typing import Annotated

from fastapi import APIRouter, Depends, Path
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db_session
from app.dependencies.pagination import PaginationParams
from app.dependencies.redis import get_redis_client
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessageResponse,
    ConversationResponse,
)
from app.schemas.response import ApiResponse
from app.schemas.user import CurrentUser
from app.services.conversation_service import (
    create_conversation,
    get_conversation_messages,
)
from app.services.conversation_service import (
    list_conversations as list_conversations_service,
)

router = APIRouter()


@router.post("/conversations", response_model=ApiResponse[ConversationResponse])
async def create_new_conversation(
    request: ConversationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ApiResponse[ConversationResponse]:
    """创建新会话"""
    result = await create_conversation(
        db=db, request=request, user_id=current_user.user_id
    )
    return ApiResponse[ConversationResponse](data=result)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[ConversationMessageResponse],
)
async def get_messages(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis_client)],
    conversation_id: str = Path(..., description="会话 ID"),
) -> ApiResponse[ConversationMessageResponse]:
    """获取会话消息列表"""
    result = await get_conversation_messages(
        db=db, conversation_id=conversation_id, redis=redis
    )
    return ApiResponse[ConversationMessageResponse](data=result)


@router.get("/conversations", response_model=ApiResponse[dict])
async def list_conversations(
    pagination: Annotated[PaginationParams, Depends(PaginationParams)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict]:
    result = await list_conversations_service(
        db=db, offset=pagination.offset, limit=pagination.page_size
    )
    "获取分页"
    return ApiResponse[dict](
        data={
            "page": pagination.page,
            "page_size": pagination.page_size,
            "offset": pagination.offset,
            "items": result,  # 这里可以返回实际的会话列表
        }
    )
