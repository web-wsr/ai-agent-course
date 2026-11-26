"""RAG 流式（source / message / done / error）的离线测试。

不连数据库、不调大模型：检索用 mock，LLM 用假 provider。

运行：
    uv run python tests/test_rag_stream.py
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import ErrorCode
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMProviderName, LLMStreamChunk
from app.repositories.knowledge_repository import knowledge_repository
from app.schemas.chat import SourceDocument
from app.schemas.rag import RAGQueryRequest
from app.services.rag_stream_service import (
    NO_SOURCE_ANSWER,
    build_retrieved_context,
    stream_rag_answer,
)

MODEL = "glm-5.3-flash"

SOURCES = [
    SourceDocument(
        document_id="doc_001",
        title="员工手册",
        content="员工入职满一年后，每年享有 5 天带薪年假。",
        score=0.92,
    ),
    SourceDocument(
        document_id="doc_002",
        title="考勤制度",
        content="年假需在当年 12 月 31 日前使用完毕。",
        score=0.81,
    ),
]


class FakeProvider:
    model = MODEL

    def __init__(self, parts: list[str] | None = None):
        self.parts = parts or ["年假", "5 天 [1]。"]
        self.calls = []

    async def stream_chat(self, request):
        self.calls.append(request)

        for part in self.parts:
            yield LLMStreamChunk(
                provider=LLMProviderName.GLM, model=self.model, content=part
            )


class FailingProvider:
    model = MODEL

    async def stream_chat(self, request):
        raise LLMProviderError(message="upstream 500", provider="glm", status_code=500)
        yield  # pragma: no cover


def parse_events(raw_events: list[str]) -> list[tuple[str, dict]]:
    events = []

    for raw in raw_events:
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

            events.append((name, json.loads("\n".join(data_lines))))

    return events


def build_request() -> RAGQueryRequest:
    return RAGQueryRequest(
        question="年假有几天？",
        knowledge_base_id="kb_001",
        top_k=5,
    )


async def collect(provider, sources: list[SourceDocument]) -> list[tuple[str, dict]]:
    with patch.object(
        knowledge_repository, "search_documents", AsyncMock(return_value=sources)
    ):
        raw = []
        async for event in stream_rag_answer(
            request=build_request(), llm_provider=provider, model=MODEL
        ):
            raw.append(event)

    return parse_events(raw)


def test_source_events_come_first():
    events = asyncio.run(collect(FakeProvider(), SOURCES))
    names = [name for name, _ in events]

    assert names[0] == "source"
    assert names.count("source") == 2
    assert names.index("source") < names.index("message")
    assert names[-1] == "done"


def test_source_event_payload():
    events = asyncio.run(collect(FakeProvider(), SOURCES))
    first = events[0][1]

    assert first["document_id"] == "doc_001"
    assert first["title"] == "员工手册"
    assert first["score"] == 0.92
    assert first["index"] == 1


def test_done_event_has_source_count():
    events = asyncio.run(collect(FakeProvider(["a", "b"]), SOURCES))
    name, data = events[-1]

    assert name == "done"
    assert data["source_count"] == 2
    assert data["finish_reason"] == "stop"


def test_prompt_receives_numbered_context():
    provider = FakeProvider(["ok"])
    asyncio.run(collect(provider, SOURCES))

    user_content = provider.calls[0].messages[-1].content

    assert "[1] 员工手册" in user_content
    assert "[2] 考勤制度" in user_content
    assert "年假有几天" in user_content


def test_uses_rag_prompt_v2_with_citation_rules():
    provider = FakeProvider(["ok"])
    asyncio.run(collect(provider, SOURCES))

    system_content = provider.calls[0].messages[0].content

    assert "引用格式要求" in system_content
    assert "无引用则不允许输出" in system_content


def test_no_source_skips_llm_and_returns_fallback():
    provider = FakeProvider()
    events = asyncio.run(collect(provider, []))

    names = [name for name, _ in events]

    assert "source" not in names
    assert names == ["message", "done"]
    assert events[0][1]["content"] == NO_SOURCE_ANSWER
    assert events[-1][1]["finish_reason"] == "no_source"
    assert provider.calls == []


def test_llm_error_emits_error_event():
    events = asyncio.run(collect(FailingProvider(), SOURCES))

    names = [name for name, _ in events]

    assert names.count("source") == 2
    assert "error" in names
    assert "done" not in names
    assert events[-1][1]["code"] == int(ErrorCode.RAG_QUERY_FAILED)


def test_context_builder_numbers_sources():
    context = build_retrieved_context(SOURCES)

    assert context.splitlines()[0].startswith("[1] 员工手册：")
    assert context.splitlines()[1].startswith("[2] 考勤制度：")


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
