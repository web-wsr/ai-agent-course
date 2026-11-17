import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock

from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.core.config import settings
from app.dependencies.redis import get_redis_client
from app.main import app
from app.redis.document_state import get_document_parse_state, set_document_parse_state
from app.redis.keys import document_parse_state_key


async def main():
    values = {}
    history = []
    started = asyncio.Event()
    redis = Mock(spec=Redis)
    redis.get = AsyncMock(side_effect=values.get)

    def store(key, value, ex=None):
        state = json.loads(value)
        values[key] = value
        history.append((state, ex))
        if state["status"] == "running":
            started.set()
        return True

    redis.set = AsyncMock(side_effect=store)

    async def test_redis():
        return redis

    await verify_state_storage(redis)
    app.dependency_overrides[get_redis_client] = test_redis
    logger = logging.getLogger("app.core.exception_handlers")
    original_handlers, original_propagate = logger.handlers, logger.propagate
    logger.handlers, logger.propagate = [logging.NullHandler()], False
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"x-api-key": settings.app_api_key},
        ) as client:
            for simulate_failure in (False, True):
                started.clear()
                submission = asyncio.create_task(client.post(
                    "/api/v1/documents/parse",
                    json={"document_id": "doc_test", "simulate_failure": simulate_failure},
                ))
                await asyncio.wait_for(started.wait(), timeout=5)
                task_id = history[-1][0]["task_id"]
                running = await client.get(f"/api/v1/documents/tasks/{task_id}")
                assert running.status_code == 200, running.text
                assert running.json()["data"]["status"] == "running"

                response = await submission
                assert response.status_code == 202, response.text
                assert response.json()["data"]["status"] == "pending"
                assert response.json()["data"]["task_id"] == task_id

                expected = "failed" if simulate_failure else "success"
                terminal = await client.get(f"/api/v1/documents/tasks/{task_id}")
                assert terminal.status_code == 200, terminal.text
                state = terminal.json()["data"]
                assert state["status"] == expected
                assert state["document_id"] == "doc_test"
                assert state["error" if simulate_failure else "result"]
                transitions = [(item["status"], ttl) for item, ttl in history
                               if item["task_id"] == task_id]
                assert transitions == [("pending", 3600), ("running", 3600), (expected, 3600)]

            missing = await client.get("/api/v1/documents/tasks/task_missing")
            assert missing.status_code == 404, missing.text
            assert missing.json()["code"] == 40400
            invalid = await client.post("/api/v1/documents/parse", json={"document_id": ""})
            assert invalid.status_code == 422, invalid.text
        print("PASS: pending/running/success/failed, JSON storage, TTL, missing task, request validation")
        print("Redis I/O mocked; actual routes and background task executed")
    finally:
        app.dependency_overrides.pop(get_redis_client, None)
        logger.handlers, logger.propagate = original_handlers, original_propagate


async def verify_state_storage(redis):
    assert await get_document_parse_state(redis, "task_missing") is None
    state = {"task_id": "task_storage", "status": "pending", "document_id": "课程文档"}
    await set_document_parse_state(redis, "task_storage", state, ttl_seconds=60)
    assert redis.set.call_args.args[0] == document_parse_state_key("task_storage")
    assert redis.set.call_args.kwargs["ex"] == 60
    assert await get_document_parse_state(redis, "task_storage") == state


if __name__ == "__main__":
    asyncio.run(main())
