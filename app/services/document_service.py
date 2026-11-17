import asyncio

from app.redis.document_state import set_document_parse_state
from redis.asyncio import Redis


async def parse_document(
    redis: Redis,
    task_id: str,
    document_id: str,
    simulate_failure: bool = False,
) -> None:
    state = {
        "task_id": task_id,
        "document_id": document_id,
        "status": "running",
    }
    await set_document_parse_state(redis=redis, task_id=task_id, state=state)

    await asyncio.sleep(2)

    if simulate_failure:
        state["status"] = "failed"
        state["error"] = "模拟文档解析失败"
    else:
        state["status"] = "success"
        state["result"] = "模拟文档解析完成"

    await set_document_parse_state(redis=redis, task_id=task_id, state=state)
