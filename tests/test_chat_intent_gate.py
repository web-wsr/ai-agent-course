"""ChatService 意图前置拦截的离线测试。

覆盖：query_order 缺订单号 → 请提供订单号；human_service → 转人工；
其余意图 → 继续走普通 LLM Chat；意图识别失败 → 降级继续回答。
不联网、不落库，LLM 用假 provider。

运行：
    uv run python tests/test_chat_intent_gate.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMProviderName, LLMResponse
from app.schemas.chat import ChatMessage, ChatRequest, MessageRole
from app.services.chat_service import (
    ASK_ORDER_ID_ANSWER,
    TRANSFER_HUMAN_ANSWER,
    chat_with_ai,
)

MODEL = "glm-5.3-flash"
NORMAL_ANSWER = "这是普通模型的回答。"


def build_request(question: str) -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role=MessageRole.USER, content=question)],
        model=MODEL,
        stream=False,
    )


def build_intent_json(
    intent: str,
    need_order_id: bool,
    reply_strategy: str,
) -> str:
    return json.dumps(
        {
            "intent": intent,
            "confidence": 0.9,
            "need_order_id": need_order_id,
            "reply_strategy": reply_strategy,
            "reason": "测试用例",
        },
        ensure_ascii=False,
    )


def is_intent_request(request) -> bool:
    """意图识别请求的系统提示词里带“意图识别器”。"""
    return any("意图识别" in message.content for message in request.messages)


class FakeProvider:
    """意图识别请求返回预设 JSON，其他请求返回普通回答。"""

    model = MODEL

    def __init__(self, intent_json: str):
        self.intent_json = intent_json
        self.calls = []

    async def chat(self, request):
        self.calls.append(request)

        content = self.intent_json if is_intent_request(request) else NORMAL_ANSWER

        return LLMResponse(
            provider=LLMProviderName.GLM,
            model=MODEL,
            content=content,
        )


class IntentBrokenProvider(FakeProvider):
    """意图识别阶段抛异常，验证主回答仍能继续。"""

    async def chat(self, request):
        if is_intent_request(request):
            self.calls.append(request)
            raise LLMProviderError(
                message="intent upstream 500", provider="glm", status_code=500
            )

        return await super().chat(request)


def test_query_order_without_order_id_short_circuits():
    provider = FakeProvider(build_intent_json("query_order", True, "ask_order_id"))

    result = asyncio.run(chat_with_ai(build_request("我的订单到哪了"), llm_provider=provider))

    assert result.answer == ASK_ORDER_ID_ANSWER
    assert len(provider.calls) == 1, "命中订单号缺失时应直接返回，不再调主模型"


def test_human_service_short_circuits():
    provider = FakeProvider(build_intent_json("human_service", False, "transfer_human"))

    result = asyncio.run(chat_with_ai(build_request("我要找人工"), llm_provider=provider))

    assert result.answer == TRANSFER_HUMAN_ANSWER
    assert len(provider.calls) == 1


def test_query_order_with_order_id_goes_to_llm():
    provider = FakeProvider(build_intent_json("query_order", False, "call_tool"))

    result = asyncio.run(
        chat_with_ai(build_request("查一下订单 10001"), llm_provider=provider)
    )

    assert result.answer == NORMAL_ANSWER
    assert len(provider.calls) == 2, "意图识别 + 普通回答各一次调用"


def test_other_intent_goes_to_llm():
    provider = FakeProvider(build_intent_json("product_question", False, "answer_directly"))

    result = asyncio.run(chat_with_ai(build_request("这个支持七天无理由吗"), llm_provider=provider))

    assert result.answer == NORMAL_ANSWER
    assert len(provider.calls) == 2


def test_intent_failure_falls_back_to_llm():
    provider = IntentBrokenProvider(build_intent_json("other", False, "answer_directly"))

    result = asyncio.run(chat_with_ai(build_request("随便聊聊"), llm_provider=provider))

    assert result.answer == NORMAL_ANSWER
    assert len(provider.calls) == 2, "意图识别失败后仍应继续调用主模型"


def test_intent_gate_response_keeps_session_id():
    request = build_request("我的订单到哪了")
    request.session_id = "s_test123"

    provider = FakeProvider(build_intent_json("query_order", True, "ask_order_id"))

    result = asyncio.run(chat_with_ai(request, llm_provider=provider))

    assert result.session_id == "s_test123"
    assert result.trace_id.startswith("trace_")
    assert result.message_id.startswith("m_")


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
