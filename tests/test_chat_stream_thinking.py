"""流式 thinking 事件的离线测试（不调用大模型、不连 Redis）。

运行：
    uv run python tests/test_chat_stream_thinking.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.llm.schemas import LLMProviderName, LLMStreamChunk
from app.schemas.chat import ChatMessage, ChatRequest, MessageRole
from app.services.chat_stream_service import stream_chat_with_ai
from app.utils.sse import THINKING_TEXT

MODEL = settings.default_model


class FakeProvider:
    """假 provider：按给定片段吐出流式 chunk。"""

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
    )


async def collect(provider, redis=None) -> list[tuple[str, dict]]:
    events = []

    async for raw in stream_chat_with_ai(
        request=build_request(),
        llm_provider=provider,
        db=None,
        redis=redis,
    ):
        events.extend(parse_events(raw))

    return events


def names(events):
    return [name for name, _ in events]


def test_first_event_is_thinking():
    events = asyncio.run(collect(FakeProvider(["你", "好"])))

    name, data = events[0]

    assert name == "thinking"
    assert data["content"] == THINKING_TEXT
    assert "message_id" in data


def test_thinking_sent_only_once_before_message():
    events = asyncio.run(collect(FakeProvider(["a", "b", "c"])))

    assert names(events).count("thinking") == 1
    assert names(events).index("thinking") < names(events).index("message")


def test_event_order():
    events = asyncio.run(collect(FakeProvider(["你", "好"])))

    assert names(events) == ["thinking", "start", "message", "message", "done"]


def test_cache_hit_skips_thinking():
    events = asyncio.run(collect(FakeProvider(["ignored"]), redis=FakeRedis("缓存的答案")))

    assert "thinking" not in names(events)
    assert names(events)[0] == "start"
    assert names(events)[-1] == "done"


def test_cache_miss_still_sends_thinking_and_writes_cache():
    redis = FakeRedis(None)
    events = asyncio.run(collect(FakeProvider(["你", "好"]), redis=redis))

    assert names(events)[0] == "thinking"
    assert redis.stored, "回答结束后应写入缓存"


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
