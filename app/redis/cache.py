# 缓存封装

import json
import hashlib

from redis.asyncio import Redis

from app.core.config import settings
from app.redis.keys import conversation_recent_messages_key
from app.schemas.chat import ChatMessage, MessageRole
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.redis.keys import chat_response_cache_key, api_key_cache_key, rag_query_cache_key, verification_code_key

async def cache_recent_messages(
    redis: Redis,
    conversation_id: str,
    messages: list[ChatMessage],
    ttl_seconds: int | None = None
):
    key = conversation_recent_messages_key(conversation_id)

    data=[
        {
            "role": message.role.value,
            "content": message.content
        }
        for message in messages
    ]

    await redis.set(
        key,
        json.dumps(data, ensure_ascii=False),
        ex=ttl_seconds or settings.redis_default_ttl_seconds
    )

async def get_cached_recent_messages(
    redis: Redis,
    conversation_id: str,
) -> list[ChatMessage] | None:
    key = conversation_recent_messages_key(conversation_id)
    value = await redis.get(key)

    if not value:
        return None

    data = json.loads(value)

    return [
        ChatMessage(
            role=MessageRole(item["role"]),
            content=item["content"],
        )
        for item in data
    ]

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

async def get_cached_chat_response(
    redis: Redis,
    question: str,
    model: str,
) -> str | None:
    key = chat_response_cache_key(hash_text(question), model)
    return await redis.get(key)


async def cache_chat_response(
        redis: Redis,
        question: str,
        answer: str,
        model: str,
        ttl_seconds: int =300,
):
    key = chat_response_cache_key(hash_text(question), model)

    await redis.set(
        key,
        answer,
        ttl_seconds,
    )



async def cache_api_key_user(
    redis: Redis,
    api_key_hash: str,
    user_id: str,
    ttl_seconds: int = 600,
):
    key = api_key_cache_key(api_key_hash)

    await redis.set(
        key,
        user_id,
        ttl_seconds,
    
)

async def get_cached_api_key_user(
    redis: Redis,
    api_key_hash: str,
) -> str | None:
    key = api_key_cache_key(api_key_hash)

    return await redis.get(key)



async def get_cached_rag_result(
    redis: Redis,
    request: RAGQueryRequest,
) -> RAGQueryResponse | None:
    query_hash = hash_text(json.dumps(request.model_dump(mode="json"), sort_keys=True))
    key = rag_query_cache_key(query_hash, request.knowledge_base_id)
    value = await redis.get(key)

    if value is None:
        return None

    return RAGQueryResponse.model_validate_json(value)


async def cache_rag_result(
    redis: Redis,
    request: RAGQueryRequest,
    result: RAGQueryResponse,
    ttl_seconds: int = 600,
) -> None:
    query_hash = hash_text(json.dumps(request.model_dump(mode="json"), sort_keys=True))
    key = rag_query_cache_key(query_hash, request.knowledge_base_id)

    await redis.set(
        key,
        result.model_dump_json(exclude={"trace_id"}),
        ex=ttl_seconds,
    )

#验证码缓存 
async def cache_verification_code(
        redis: Redis,
        email: str,
        code: str,
        ttl_seconds: int =3600,
    ) -> None:
    key = verification_code_key(email)
    await redis.set(
        key,
        code,
        ex=ttl_seconds,
    )

async def get_verification_code(
        redis: Redis,
        email: str,
    ) -> str | None:
    key = verification_code_key(email)
    return await redis.get(key)

