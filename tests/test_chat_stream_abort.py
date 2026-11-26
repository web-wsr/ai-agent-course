"""流式请求“停止生成”的离线测试。

验证：前端 abort（等价于 http.disconnect）后，后端 is_disconnected() 为 True，
停止继续输出，并且不把半截回答写进缓存。

运行：
    uv run python tests/test_chat_stream_abort.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.v1.chat import chat_stream
from app.core.config import settings
from app.llm.schemas import LLMProviderName, LLMStreamChunk
from app.schemas.chat import ChatMessage, ChatRequest, MessageRole

MODEL = settings.default_model


class FakeProvider:
    model = MODEL

    def __init__(self, parts: list[str]):
        self.parts = parts

    async def stream_chat(self, request):
        for part in self.parts:
            yield LLMStreamChunk(
                provider=LLMProviderName.GLM,
                model=self.model,
                content=part,
            )


class FakeRedis:
    def __init__(self, cached: str | None = None):
        self.cached = cached
        self.stored: dict[str, str] = {}

    async def get(self, key):
        return self.cached

    async def set(self, key, value, ex=None):
        self.stored[key] = value


class FakeRequest:
    """模拟客户端连接：allowed 个事件之后视为已断开。"""

    def __init__(self, allowed: int | None = None):
        self.allowed = allowed
        self.checks = 0

    async def is_disconnected(self) -> bool:
        self.checks += 1

        if self.allowed is None:
            return False

        return self.checks > self.allowed


def parse_events(raw: str) -> list[tuple[str, dict]]:
    events = []

    for block in raw.split("\n\n"):
        if not block.strip():
            continue

        name = "message"
        data_lines = []

        for line in block.splitlines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))

        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((name, payload))

    return events


def build_request() -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="你好")],
        model=MODEL,
        stream=True,
        session_id=None,
    )


async def run(allowed: int | None, redis=None) -> list[tuple[str, dict]]:
    response = await chat_stream(
        request_body=build_request(),
        request=FakeRequest(allowed),
        current_user=None,
        db=None,
        redis=redis,
        llm_provider=FakeProvider(["你", "好"]),
    )

    events = []
    async for chunk in response.body_iterator:
        events.extend(parse_events(chunk))

    return events


def test_no_disconnect_streams_to_done():
    events = asyncio.run(run(allowed=None))

    assert [name for name, _ in events] == [
        "thinking",
        "start",
        "message",
        "message",
        "done",
    ]


def test_disconnect_midway_stops_output():
    """允许 3 个事件通过（thinking/start/第 1 个 message），之后断开。"""
    events = asyncio.run(run(allowed=3))

    assert [name for name, _ in events] == ["thinking", "start", "message"]


def test_disconnect_immediately_emits_nothing():
    events = asyncio.run(run(allowed=0))

    assert events == []


def test_disconnect_skips_cache_write():
    redis = FakeRedis()

    events = asyncio.run(run(allowed=2, redis=redis))

    assert [name for name, _ in events] == ["thinking", "start"]
    assert redis.stored == {}, "中断后不应把半截回答写入缓存"


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
