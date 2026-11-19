import asyncio
import json
from unittest.mock import patch

import httpx
from app.core.config import settings
from app.llm.errors import LLMProviderConfigError
from app.llm.factory import LLMProviderFactory, infer_provider_from_model
from app.llm.providers import DeepSeekProvider, GLMProvider
from app.llm.schemas import LLMMessage, LLMProviderName, LLMRequest, LLMRole


async def main():
    with (
        patch.object(settings, "glm_api_key", "test-glm-key"),
        patch.object(settings, "glm_base_url", "https://open.bigmodel.cn/api/paas/v4/"),
        patch.object(settings, "llm_timeout_seconds", 60),
    ):
        verify_factory()
        await verify_chat_and_stream()
        verify_missing_key()
    print(
        "PASS: GLM factory selection, configuration, chat, streaming, usage and finish_reason"
    )
    print("HTTP requests mocked; no real API calls or API keys transmitted")


def verify_factory():
    provider = LLMProviderFactory.create("glm")
    assert isinstance(provider, GLMProvider)
    assert provider.provider_name == LLMProviderName.GLM
    assert provider.default_model == "glm-5.3-flash"
    assert provider.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert provider.timeout_seconds == 60
    assert isinstance(LLMProviderFactory.create(LLMProviderName.GLM), GLMProvider)
    for model in ("glm-5.3-flash", "GLM-5.3-Flash"):
        assert infer_provider_from_model(model) == LLMProviderName.GLM
        with patch.object(settings, "default_model", model):
            assert isinstance(LLMProviderFactory.create(), GLMProvider)
    with patch.object(settings, "deepseek_api_key", "test-deepseek-key"):
        assert isinstance(LLMProviderFactory.create("deepseek"), DeepSeekProvider)
    assert infer_provider_from_model("qwen-plus") == LLMProviderName.QWEN


async def verify_chat_and_stream():
    content = "AI Agent 可以调用工具。"
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    clients = []
    payloads = []

    def respond(request):
        assert (
            str(request.url) == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        )
        assert request.headers["Authorization"] == "Bearer test-glm-key"
        payload = json.loads(request.content)
        payloads.append(payload)
        assert payload["model"] == "glm-5.3-flash"
        assert payload["messages"] == [{"role": "user", "content": "什么是 AI Agent？"}]
        assert payload["max_tokens"] == 128
        assert "stream_options" not in payload
        if not payload["stream"]:
            return httpx.Response(
                200,
                json={
                    "model": "glm-5.3-flash",
                    "choices": [{"message": {"role": "assistant", "content": content}}],
                    "usage": usage,
                },
            )
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "AI Agent "}}]},
            {"choices": [{"delta": {"content": "可以调用工具。"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": usage},
        ]
        body = "".join(
            f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(body + "data: [DONE]\n\n").encode(),
        )

    def test_client(timeout_seconds):
        assert timeout_seconds == 60
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(respond), timeout=timeout_seconds
        )
        clients.append(client)
        return client

    provider = GLMProvider()
    request = LLMRequest(
        model="glm-5.3-flash",
        messages=[LLMMessage(role=LLMRole.USER, content="什么是 AI Agent？")],
        max_tokens=128,
    )
    with patch(
        "app.llm.providers.openai_compatible.create_llm_http_client", test_client
    ):
        response = await provider.chat(request)
        assert response.provider == LLMProviderName.GLM
        assert response.content == content
        assert response.usage.model_dump() == usage
        chunks = [chunk async for chunk in provider.stream_chat(request)]
        assert all(chunk.provider == LLMProviderName.GLM for chunk in chunks)
        assert "".join(chunk.content for chunk in chunks) == content
        assert chunks[-1].finish_reason == "stop"
        assert chunks[-1].usage.model_dump() == usage
    assert [payload["stream"] for payload in payloads] == [False, True]
    assert all(client.is_closed for client in clients)


def verify_missing_key():
    with patch.object(settings, "glm_api_key", ""):
        try:
            GLMProvider()
        except LLMProviderConfigError as exc:
            assert exc.provider == "glm"
        else:
            raise AssertionError(
                "Missing GLM API key should raise LLMProviderConfigError"
            )


if __name__ == "__main__":
    asyncio.run(main())
