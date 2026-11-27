"""订单信息抽取（OrderInfoExtractOutput）的离线测试。

覆盖：schema 归一化与校验、服务调用、修复重试、API 返回结构。
不联网，LLM 用假 provider。

运行：
    uv run python tests/test_order_info_extract.py
"""

import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.v1.structured_outputs import (
    OrderInfoExtractRequest,
    extract_order_info,
)
from app.core.exceptions import AppException, ErrorCode
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMProviderName, LLMResponse
from app.prompts.registry import prompt_registry
from app.prompts.renderer import extract_variables
from app.services.structured_output_service import structured_output_service
from app.structured_outputs.schemas import OrderInfoExtractOutput

MODEL = "glm-5.3-flash"
PROMPT_ID = "order_info_extract_structured"

FULL_JSON = json.dumps(
    {
        "order_id": "10001",
        "phone_last4": "8848",
        "has_required_info": True,
        "missing_fields": [],
    },
    ensure_ascii=False,
)

PARTIAL_JSON = json.dumps(
    {
        "order_id": None,
        "phone_last4": "8848",
        "has_required_info": False,
        "missing_fields": ["order_id"],
    },
    ensure_ascii=False,
)


class FakeProvider:
    """按顺序返回预设内容，并记录收到的请求。"""

    model = MODEL

    def __init__(self, contents: list[str]):
        self.contents = contents
        self.calls = []

    async def chat(self, request):
        self.calls.append(request)
        index = min(len(self.calls) - 1, len(self.contents) - 1)

        return LLMResponse(
            provider=LLMProviderName.GLM,
            model=MODEL,
            content=self.contents[index],
        )


class FailingProvider:
    model = MODEL

    async def chat(self, request):
        raise LLMProviderError(message="upstream 500", provider="glm", status_code=500)


async def run_service(provider, question: str = "订单 10001，手机号尾号 8848"):
    return await structured_output_service.extract_order_info(
        user_question=question,
        model=MODEL,
        llm_provider=provider,
    )


def test_full_info_extracted():
    provider = FakeProvider([FULL_JSON])
    result = asyncio.run(run_service(provider))

    assert result.order_id == "10001"
    assert result.phone_last4 == "8848"
    assert result.has_required_info is True
    assert result.missing_fields == []


def test_missing_order_id_detected():
    provider = FakeProvider([PARTIAL_JSON])
    result = asyncio.run(run_service(provider))

    assert result.order_id is None
    assert result.has_required_info is False
    assert result.missing_fields == ["order_id"]


def test_service_requests_json_mode():
    provider = FakeProvider([FULL_JSON])
    asyncio.run(run_service(provider))

    request = provider.calls[0]

    assert request.response_format == {"type": "json_object"}
    assert request.temperature == 0.1
    assert request.stream is False
    assert "订单 10001" in request.messages[-1].content


def test_has_required_info_is_reconciled_with_real_fields():
    """模型自报 true 但缺 order_id 时，以实际字段为准。"""
    raw = json.dumps(
        {
            "order_id": None,
            "phone_last4": "8848",
            "has_required_info": True,
            "missing_fields": [],
        },
        ensure_ascii=False,
    )

    result = asyncio.run(run_service(FakeProvider([raw])))

    assert result.has_required_info is False
    assert result.missing_fields == ["order_id"]


def test_invalid_output_is_repaired_once():
    bad = "我觉得这个订单是 10001，尾号 8848"
    provider = FakeProvider([bad, FULL_JSON])

    result = asyncio.run(run_service(provider))

    assert len(provider.calls) == 2, "第一次解析失败应触发一次修复调用"
    assert result.order_id == "10001"
    assert result.has_required_info is True


def test_llm_error_raises_app_exception():
    try:
        asyncio.run(run_service(FailingProvider()))
    except AppException as exc:
        assert exc.code == int(ErrorCode.LLM_CALL_FAILED)
        assert exc.data["task"] == "order_info_extract"
    else:
        raise AssertionError("模型调用失败应抛 AppException")


def test_empty_strings_normalized_to_none():
    raw = json.dumps(
        {
            "order_id": "无",
            "phone_last4": "",
            "has_required_info": False,
            "missing_fields": ["order_id", "phone_last4"],
        },
        ensure_ascii=False,
    )

    result = OrderInfoExtractOutput.model_validate_json(raw)

    assert result.order_id is None
    assert result.phone_last4 is None
    assert result.missing_fields == ["order_id", "phone_last4"]


def test_invalid_phone_last4_rejected():
    raw = json.dumps(
        {
            "order_id": "10001",
            "phone_last4": "88481",
            "has_required_info": True,
            "missing_fields": [],
        },
        ensure_ascii=False,
    )

    try:
        OrderInfoExtractOutput.model_validate_json(raw)
    except ValidationError as exc:
        assert "phone_last4" in str(exc)
    else:
        raise AssertionError("phone_last4 不是 4 位数字时应当校验失败")


def test_prompt_registered_and_renderable():
    prompt = prompt_registry.get(prompt_id=PROMPT_ID, version="v1")

    placeholders = set()
    for message in prompt.messages:
        placeholders |= extract_variables(message.template)

    assert placeholders == {"user_question"}
    assert prompt.required_variables == ["user_question"]

    system_text = prompt.messages[0].template
    for field_name in ("order_id", "phone_last4", "has_required_info", "missing_fields"):
        assert field_name in system_text


def test_api_returns_api_response():
    provider = FakeProvider([FULL_JSON])

    response = asyncio.run(
        extract_order_info(
            request=OrderInfoExtractRequest(question="订单 10001，尾号 8848", model=MODEL),
            current_user=None,
            llm_provider=provider,
        )
    )

    assert response.code == 0
    assert isinstance(response.data, OrderInfoExtractOutput)
    assert response.data.order_id == "10001"
    assert response.data.has_required_info is True


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
