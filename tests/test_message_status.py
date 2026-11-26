"""消息 status 落库的离线测试（mock 掉仓储，不连数据库）。

覆盖：
- 正常结束 -> completed
- 模型异常 -> failed
- 用户中断（生成器被关闭）-> interrupted

运行：
    uv run python tests/test_message_status.py
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMProviderName, LLMStreamChunk
from app.repositories.conversation_repository import conversation_repository
from app.schemas.chat import ChatMessage, ChatRequest, MessageRole, MessageStatus
from app.services.chat_stream_service import stream_chat_with_ai

MODEL = settings.default_model
DB = object()  # 只用作“有 db”的哨兵，仓储已 mock


class FakeProvider:
    model = MODEL

    def __init__(self, parts: list[str]):
        self.parts = parts

    async def stream_chat(self, request):
        for part in self.parts:
            yield LLMStreamChunk(
                provider=LLMProviderName.GLM, model=self.model, content=part
            )


class FailingProvider:
    model = MODEL

    async def stream_chat(self, request):
        yield LLMStreamChunk(
            provider=LLMProviderName.GLM, model=self.model, content="半"
        )
        raise LLMProviderError(message="upstream 500", provider="glm", status_code=500)


def build_request() -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="你好")],
        model=MODEL,
        stream=True,
        session_id="c_test",
    )


def parse_names(events: list[str]) -> list[str]:
    names = []

    for raw in events:
        for block in raw.split("\n\n"):
            for line in block.splitlines():
                if line.startswith("event: "):
                    names.append(line.removeprefix("event: ").strip())
                    break

    return names


async def drain(provider) -> tuple[list[str], AsyncMock]:
    mock = AsyncMock(return_value=None)

    with patch.object(conversation_repository, "add_message", mock):
        events = []
        async for event in stream_chat_with_ai(
            request=build_request(),
            llm_provider=provider,
            db=DB,
        ):
            events.append(event)

    return events, mock


async def drain_then_close(provider) -> tuple[list[str], AsyncMock]:
    """模拟前端点停止：拿到前 3 个事件后关闭生成器。"""
    mock = AsyncMock(return_value=None)

    with patch.object(conversation_repository, "add_message", mock):
        generator = stream_chat_with_ai(
            request=build_request(),
            llm_provider=provider,
            db=DB,
        )

        events = []
        async for event in generator:
            events.append(event)
            if len(events) >= 3:
                break

        await generator.aclose()

    return events, mock


def assistant_call(mock: AsyncMock) -> dict:
    calls = [
        call.kwargs
        for call in mock.await_args_list
        if call.kwargs.get("role") == MessageRole.ASSISTANT.value
    ]
    assert calls, "应当写入一条 assistant 消息"
    return calls[-1]


def test_completed_on_normal_finish():
    events, mock = asyncio.run(drain(FakeProvider(["你", "好"])))

    assert parse_names(events)[-1] == "done"
    assert assistant_call(mock)["status"] == MessageStatus.COMPLETED.value
    assert assistant_call(mock)["content"] == "你好"


def test_failed_on_llm_error():
    events, mock = asyncio.run(drain(FailingProvider()))

    names = parse_names(events)
    assert "error" in names
    assert "done" not in names
    assert assistant_call(mock)["status"] == MessageStatus.FAILED.value
    assert assistant_call(mock)["content"] == "半"


def test_interrupted_when_generator_closed():
    events, mock = asyncio.run(drain_then_close(FakeProvider(["你", "好", "呀"])))

    assert parse_names(events) == ["thinking", "start", "message"]
    assert assistant_call(mock)["status"] == MessageStatus.INTERRUPTED.value
    assert assistant_call(mock)["content"] == "你"


def test_user_message_always_completed():
    _, mock = asyncio.run(drain(FakeProvider(["你"])))

    user_calls = [
        call.kwargs
        for call in mock.await_args_list
        if call.kwargs.get("role") == MessageRole.USER.value
    ]

    assert user_calls
    assert all(
        call.get("status") in (None, MessageStatus.COMPLETED.value)
        for call in user_calls
    )


def test_json_events_are_valid_sse():
    events, _ = asyncio.run(drain(FakeProvider(["你"])))

    for raw in events:
        assert raw.endswith("\n\n")
        for block in raw.split("\n\n"):
            for line in block.splitlines():
                if line.startswith("data: "):
                    json.loads(line.removeprefix("data: "))


def main():
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]

    for test in tests:
        test()
        print(f"PASS  {test.__name__}")

    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    main()
