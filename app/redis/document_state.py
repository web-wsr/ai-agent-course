import json
from typing import Any

from redis.asyncio import Redis

from app.redis.keys import document_parse_state_key


async def set_document_parse_state(
    redis: Redis,
    task_id: str,
    state: dict[str, Any],
    ttl_seconds: int = 3600,
) -> None:
    key = document_parse_state_key(task_id)
    await redis.set(key, json.dumps(state, ensure_ascii=False), ex=ttl_seconds)


async def get_document_parse_state(
    redis: Redis,
    task_id: str,
) -> dict[str, Any] | None:
    key = document_parse_state_key(task_id)
    value = await redis.get(key)
    if value is None:
        return None
    return json.loads(value)
