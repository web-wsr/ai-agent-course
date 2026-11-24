from app.core.logging import get_logger
from app.redis.cache import cache_recent_messages, get_cached_recent_messages
from app.repositories.conversation_repository import conversation_repository
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationMessageResponse,
    ConversationResponse,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def create_conversation(
    db: AsyncSession, request: ConversationCreateRequest, user_id: str | None = None
) -> ConversationResponse:
    conversation = await conversation_repository.create(
        db=db, request=request, user_id=user_id
    )

    return ConversationResponse(
        conversation_id=conversation.id,
        created_at=conversation.created_at,
        status=conversation.status,
        title=conversation.title,
        updated_at=conversation.updated_at,
    )


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: str,
    redis: Redis | None = None,
) -> ConversationMessageResponse:
    if redis:
        cached_messages = await get_cached_recent_messages(
            redis=redis, conversation_id=conversation_id
        )
        print("cached_messages", cached_messages)
        if cached_messages is not None:
            logger.info("conversation_messages_cache_hit")
            return ConversationMessageResponse(
                conversation_id=conversation_id, messages=cached_messages
            )

    messages = await conversation_repository.get_messages(
        db=db, conversation_id=conversation_id
    )
    logger.info("conversation_messages_cache_miss")

    if redis:
        await cache_recent_messages(
            redis=redis,
            conversation_id=conversation_id,
            messages=messages[-10:],
        )

    return ConversationMessageResponse(
        conversation_id=conversation_id, messages=messages
    )


async def list_conversations(
    db: AsyncSession, offset: int = 0, limit: int = 10
) -> list[ConversationResponse]:
    conversations = await conversation_repository.list(
        db=db, offset=offset, limit=limit
    )

    return [
        ConversationResponse(
            conversation_id=conversation.id,
            title=conversation.title,
            status=conversation.status,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for conversation in conversations
    ]
