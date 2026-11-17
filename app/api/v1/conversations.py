from fastapi import APIRouter, Path, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis


from app.dependencies.redis import get_redis_client
from app.dependencies.database import get_db_session
from app.dependencies.auth import get_current_user
from app.schemas.user import CurrentUser

from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessageResponse,
    ConversationResponse
)
from app.schemas.response import ApiResponse
from app.services.conversation_service import (
    create_conversation,
    get_conversation_messages,
    list_conversations as list_conversations_service,
)

from app.dependencies.pagination import PaginationParams

router = APIRouter()

@router.post("/conversations", response_model=ApiResponse[ConversationResponse])
async def create_new_conversation(
    request: ConversationCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user)
) -> ApiResponse[ConversationResponse]:
    """创建新会话"""
    result = await create_conversation(
        db=db,
        request=request,
        user_id=current_user.user_id
    )
    return ApiResponse[ConversationResponse](
        data=result
    )

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[ConversationMessageResponse]
)
async def get_messages(
    conversation_id: str = Path(..., description="会话 ID"),
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
) -> ApiResponse[ConversationMessageResponse]:
    """获取会话消息列表"""
    result = await get_conversation_messages(
        db=db,
        conversation_id=conversation_id,
        redis=redis
    )
    return ApiResponse[ConversationMessageResponse](
        data=result
    )

@router.get("/conversations", response_model=ApiResponse[dict])
async def list_conversations(
    pagination: PaginationParams = Depends(PaginationParams),
    db: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    result = await list_conversations_service(
        db=db,
        offset=pagination.offset,
        limit=pagination.page_size
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
