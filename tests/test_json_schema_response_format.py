"""use_json_schema 开关与回退逻辑的离线测试。

运行：
    uv run python tests/test_json_schema_response_format.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio

from app.core.exceptions import AppException, ErrorCode
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMProviderName, LLMResponse
from app.services.structured_output_service import (
    is_json_schema_unsupported,
    structured_output_service,
)
from app.structured_outputs.response_format import (
    build_json_object_response_format,
)

MODEL = "glm-5.3-flash"

ORDER_JSON = json.dumps(
    {
        "order_id": "10001",
        "phone_last4": "8848",
        "has_required_info": True,
        "missing_fields": [],
    },
    ensure_ascii=False,
)

INTENT_JSON = json.dumps(
    {
        "intent": "query_order",
        "confidence": 0.9,
        "need_order_id": False,
        "reply_strategy": "answer_directly",
        "reason": "用户查询订单状态",
    },
    ensure_ascii=False,
)


class ScriptedProvider:
    """按顺序返回内容或抛异常，并记录每次请求。"""

    model = MODEL

    def __init__(self, steps: list):
        self.steps = steps
        self.calls = []

    async def chat(self, request):
        self.calls.append(request)
        step = self.steps[min(len(self.calls) - 1, len(self.steps) - 1)]

        if isinstance(step, Exception):
            raise step

        return LLMResponse(
            provider=LLMProviderName.GLM,
            model=MODEL,
            content=step,
        )


def schema_unsupported_error() -> LLMProviderError:
    return LLMProviderError(
        message="大模型 HTTP 调用失败",
        provider="glm",
        status_code=400,
        raw_error=(
            '{"error":{"code":"1211","message":'
            '"response_format type json_schema is not supported"}}'
        ),
    )


async def call_order_info(provider, use_json_schema: bool):
    return await structured_output_service.extract_order_info(
        user_question="订单 10001，尾号 8848",
        model=MODEL,
        llm_provider=provider,
        use_json_schema=use_json_schema,
    )


def test_default_uses_json_object():
    provider = ScriptedProvider([ORDER_JSON])
    asyncio.run(call_order_info(provider, use_json_schema=False))

    assert provider.calls[0].response_format == build_json_object_response_format()


def test_use_json_schema_builds_schema_format():
    provider = ScriptedProvider([ORDER_JSON])
    asyncio.run(call_order_info(provider, use_json_schema=True))

    response_format = provider.calls[0].response_format

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "order_info_extract"
    assert response_format["json_schema"]["strict"] is True
    assert "order_id" in response_format["json_schema"]["schema"]["properties"]


def test_intent_classification_uses_expected_schema_name():
    provider = ScriptedProvider([INTENT_JSON])

    asyncio.run(
        structured_output_service.classify_intent(
            user_question="我的订单到哪了",
            model=MODEL,
            llm_provider=provider,
            use_json_schema=True,
        )
    )

    response_format = provider.calls[0].response_format

    assert response_format["json_schema"]["name"] == "intent_classification"
    assert response_format["json_schema"]["schema"]["title"] == (
        "IntentClassificationOutput"
    )


def test_fallback_to_json_object_when_unsupported():
    provider = ScriptedProvider([schema_unsupported_error(), ORDER_JSON])

    result = asyncio.run(call_order_info(provider, use_json_schema=True))

    assert len(provider.calls) == 2, "不支持时应回退重试一次"
    assert provider.calls[0].response_format["type"] == "json_schema"
    assert provider.calls[1].response_format == build_json_object_response_format()
    assert result.order_id == "10001"


def test_no_fallback_without_use_json_schema():
    provider = ScriptedProvider([schema_unsupported_error(), ORDER_JSON])

    try:
        asyncio.run(call_order_info(provider, use_json_schema=False))
    except AppException as exc:
        assert exc.code == int(ErrorCode.LLM_CALL_FAILED)
    else:
        raise AssertionError("未开启 json_schema 时不该回退，应直接抛 AppException")

    assert len(provider.calls) == 1


def test_no_fallback_on_server_error():
    provider = ScriptedProvider(
        [
            LLMProviderError(
                message="大模型 HTTP 调用失败",
                provider="glm",
                status_code=500,
                raw_error='{"error":"internal error"}',
            ),
            ORDER_JSON,
        ]
    )

    try:
        asyncio.run(call_order_info(provider, use_json_schema=True))
    except AppException:
        pass
    else:
        raise AssertionError("500 不该被当成“不支持 json_schema”")

    assert len(provider.calls) == 1


def test_no_fallback_on_unrelated_400():
    provider = ScriptedProvider(
        [
            LLMProviderError(
                message="大模型 HTTP 调用失败",
                provider="glm",
                status_code=400,
                raw_error='{"error":{"message":"invalid api key"}}',
            ),
            ORDER_JSON,
        ]
    )

    try:
        asyncio.run(call_order_info(provider, use_json_schema=True))
    except AppException:
        pass
    else:
        raise AssertionError("鉴权失败的 400 不该被当成“不支持 json_schema”")

    assert len(provider.calls) == 1


def test_is_json_schema_unsupported_helper():
    assert is_json_schema_unsupported(schema_unsupported_error()) is True

    assert (
        is_json_schema_unsupported(
            LLMProviderError(
                message="大模型 HTTP 调用失败",
                provider="glm",
                status_code=400,
                raw_error='{"error":{"message":"response_format json_schema invalid"}}',
            )
        )
        is False
    )

    assert (
        is_json_schema_unsupported(
            LLMProviderError(
                message="大模型 HTTP 调用失败",
                provider="glm",
                status_code=500,
                raw_error="response_format json_schema is not supported",
            )
        )
        is False
    )


def test_api_passes_use_json_schema_flag():
    from app.api.v1.structured_outputs import (
        OrderInfoExtractRequest,
        extract_order_info,
    )

    provider = ScriptedProvider([ORDER_JSON])

    asyncio.run(
        extract_order_info(
            request=OrderInfoExtractRequest(
                question="订单 10001，尾号 8848",
                model=MODEL,
                use_json_schema=True,
            ),
            current_user=None,
            llm_provider=provider,
        )
    )

    assert provider.calls[0].response_format["type"] == "json_schema"


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
