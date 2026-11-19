import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from app.core.config import Settings, settings
from app.llm.factory import LLMProviderFactory
from app.llm.schemas import LLMMessage, LLMRequest, LLMRole


async def main():
    verify_settings()
    with patch.multiple(
        settings,
        deepseek_api_key="test-deepseek-key",
        dashscope_api_key="test-qwen-key",
        openai_api_key="test-openai-key",
        glm_api_key="test-glm-key",
    ):
        for seconds in (60, 7):
            with patch.object(settings, "llm_timeout_seconds", seconds):
                await verify_provider_timeouts(seconds)
    print(
        "PASS: default 60, .env override, environment override, "
        "all provider HTTP read timeouts and GLM streaming"
    )
    print(
        "HTTP requests mocked; actual Settings, providers "
        "and HTTP client factory executed"
    )


def verify_settings():
    with patch.dict(os.environ, {}, clear=True), TemporaryDirectory() as directory:
        assert Settings(_env_file=None).llm_timeout_seconds == 60
        env_file = Path(directory) / ".env"
        env_file.write_text("LLM_TIMEOUT_SECONDS=7\n")
        assert Settings(_env_file=env_file).llm_timeout_seconds == 7
        with patch.dict(os.environ, {"LLM_TIMEOUT_SECONDS": "11"}):
            assert Settings(_env_file=env_file).llm_timeout_seconds == 11


async def verify_provider_timeouts(seconds):
    original_client = httpx.AsyncClient
    clients = []
    timeouts = []

    def respond(request):
        timeout = request.extensions["timeout"]
        assert timeout == {"connect": 10, "read": seconds, "write": 10, "pool": 10}
        timeouts.append(timeout)
        payload = json.loads(request.content)
        if payload.get("stream"):
            chunk = {
                "choices": [
                    {"delta": {"content": "测试响应"}, "finish_reason": "stop"}
                ]
            }
            body = (
                f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                "data: [DONE]\n\n"
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=body.encode(),
            )
        if request.url.path.endswith("/responses"):
            return httpx.Response(
                200, json={"model": payload["model"], "output_text": "测试响应"}
            )
        return httpx.Response(
            200,
            json={
                "model": payload["model"],
                "choices": [{"message": {"content": "测试响应"}}],
            },
        )

    def test_client(**kwargs):
        assert kwargs["timeout"].read == seconds
        client = original_client(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    with patch("app.llm.http_client.httpx.AsyncClient", test_client):
        for name, model in {
            "deepseek": "deepseek-chat",
            "qwen": "qwen-plus",
            "openai": "gpt-4o-mini",
            "glm": "glm-5.3-flash",
        }.items():
            provider = LLMProviderFactory.create(name)
            assert provider.timeout_seconds == seconds
            request = LLMRequest(
                model=model,
                messages=[LLMMessage(role=LLMRole.USER, content="测试超时配置")],
            )
            response = await provider.chat(request)
            assert response.content == "测试响应"
            if name == "glm":
                chunks = [chunk async for chunk in provider.stream_chat(request)]
                assert "".join(chunk.content for chunk in chunks) == "测试响应"
    assert len(timeouts) == 5
    assert all(client.is_closed for client in clients)


if __name__ == "__main__":
    asyncio.run(main())
