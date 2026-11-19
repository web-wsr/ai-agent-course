import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock, patch

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies.database import get_db_session
from app.dependencies.redis import get_redis_client
from app.llm.factory import infer_provider_from_model
from app.llm.schemas import LLMProviderName
from app.main import app


async def main():
    with patch.multiple(
        settings,
        default_model="glm-5.3-flash",
        supported_models="deepseek-chat,qwen-plus,gpt-4o-mini,glm-5.3-flash",
        app_api_key="test-app-key",
        deepseek_api_key="test-deepseek-key",
        deepseek_base_url="https://api.deepseek.com",
        dashscope_api_key="test-qwen-key",
        qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        openai_api_key="test-openai-key",
        openai_base_url="https://api.openai.com/v1",
        glm_api_key="test-glm-key",
        glm_base_url="https://open.bigmodel.cn/api/paas/v4",
    ):
        await verify_routing()
    print("PASS: request.model selects DeepSeek/Qwen/OpenAI/GLM; default provider does not override it")
    print("PASS: the same question uses a separate cache per model")
    print("HTTP and Redis I/O mocked; no external services accessed")


async def verify_routing():
    cases = {
        "deepseek-chat": (LLMProviderName.DEEPSEEK, "api.deepseek.com", "/chat/completions", "test-deepseek-key"),
        "qwen-plus": (LLMProviderName.QWEN, "dashscope.aliyuncs.com", "/compatible-mode/v1/chat/completions", "test-qwen-key"),
        "gpt-4o-mini": (LLMProviderName.OPENAI, "api.openai.com", "/v1/responses", "test-openai-key"),
        "glm-5.3-flash": (LLMProviderName.GLM, "open.bigmodel.cn", "/api/paas/v4/chat/completions", "test-glm-key"),
    }
    values = {}
    calls = []
    redis = Mock(spec=Redis)
    redis.get = AsyncMock(side_effect=values.get)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=60)

    def store(key, value, ex=None):
        values[key] = value
        return True

    redis.set = AsyncMock(side_effect=store)

    async def test_redis():
        return redis

    async def test_db():
        async with AsyncSession() as db:
            yield db

    def respond(request):
        payload = json.loads(request.content)
        model = payload["model"]
        _, host, path, key = cases[model]
        assert request.url.host == host
        assert request.url.path == path
        assert request.headers["Authorization"] == f"Bearer {key}"
        calls.append(model)
        if path == "/v1/responses":
            return httpx.Response(200, json={
                "model": model, "output_text": f"reply:{model}",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            })
        return httpx.Response(200, json={
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": f"reply:{model}"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    def test_http_client(timeout_seconds):
        return httpx.AsyncClient(transport=httpx.MockTransport(respond), timeout=timeout_seconds)

    app.dependency_overrides[get_redis_client] = test_redis
    app.dependency_overrides[get_db_session] = test_db
    try:
        with (
            patch("app.llm.providers.openai_compatible.create_llm_http_client", test_http_client),
            patch("app.llm.providers.openai.create_llm_http_client", test_http_client),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                headers={"x-api-key": "test-app-key", "x-user-id": "u_test", "x-username": "tester"},
            ) as client:
                for model, (provider, _, _, _) in cases.items():
                    assert infer_provider_from_model(model) == provider
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": "同一个问题"}],
                    }
                    if model == "deepseek-chat":
                        with patch.object(settings, "glm_api_key", ""):
                            response = await client.post("/api/v1/chat", json=payload)
                    else:
                        response = await client.post("/api/v1/chat", json=payload)
                    assert response.status_code == 200, response.text
                    data = response.json()["data"]
                    assert data["answer"] == f"reply:{model}"
                    assert data["model"] == model
                    assert data["usage"]["total_tokens"] == 15
                assert calls == list(cases)
                assert len(values) == 4

                for model in cases:
                    response = await client.post("/api/v1/chat", json={
                        "model": model,
                        "messages": [{"role": "user", "content": "同一个问题"}],
                    })
                    assert response.status_code == 200, response.text
                    assert response.json()["data"]["answer"] == f"reply:{model}"
                    assert response.json()["data"]["usage"]["total_tokens"] == 0
                assert calls == list(cases)
    finally:
        app.dependency_overrides.pop(get_redis_client, None)
        app.dependency_overrides.pop(get_db_session, None)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.ERROR)
    asyncio.run(main())
