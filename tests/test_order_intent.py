"""订单意图识别的离线测试（不调用大模型）。

运行：
    uv run python tests/test_order_intent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import AppException, ErrorCode
from app.prompts.registry import prompt_registry
from app.prompts.renderer import extract_variables, render_prompt
from app.schemas.order_intent import OrderIntent, OrderIntentResult
from app.services.order_intent_service import parse_order_intent

PROMPT_ID = "order_intent"
VERSION = "v1"

VALID_JSON = """
{
  "intent": "refund",
  "confidence": 0.88,
  "order_no": "10001",
  "reason": "用户要求退款",
  "need_human": false
}
"""


def _expect_app_exception(raw: str) -> AppException:
    try:
        parse_order_intent(raw)
    except AppException as exc:
        return exc

    raise AssertionError(f"非法输出应当抛 AppException：{raw}")


def test_all_four_intents_accepted():
    for intent in OrderIntent:
        result = parse_order_intent(VALID_JSON.replace("refund", intent.value))
        assert result.intent == intent


def test_parse_plain_json():
    result = parse_order_intent(VALID_JSON)

    assert result.intent is OrderIntent.REFUND
    assert result.confidence == 0.88
    assert result.order_no == "10001"
    assert result.need_human is False


def test_parse_with_code_fence_and_chatter():
    raw = "识别结果如下：\n```json\n" + VALID_JSON + "\n```\n希望有帮助。"

    result = parse_order_intent(raw)

    assert result.intent is OrderIntent.REFUND


def test_extra_fields_are_ignored():
    raw = VALID_JSON.replace("{", '{"model_comment": "多余字段",')

    result = parse_order_intent(raw)

    assert result.intent is OrderIntent.REFUND


def test_invalid_intent_raises_app_exception():
    exc = _expect_app_exception(VALID_JSON.replace("refund", "complaint"))

    assert exc.code == int(ErrorCode.LLM_RESPONSE_PARSE_FAILED)
    assert exc.status_code == 500
    assert exc.data["errors"][0]["field"] == "intent"


def test_missing_required_field_raises_app_exception():
    raw = """
    {
      "intent": "logistics",
      "confidence": 0.7,
      "order_no": null,
      "need_human": false
    }
    """

    exc = _expect_app_exception(raw)

    assert exc.data["errors"][0]["field"] == "reason"


def test_malformed_json_raises_app_exception():
    exc = _expect_app_exception('{"intent": "refund", "confidence": }')

    assert exc.code == int(ErrorCode.LLM_RESPONSE_PARSE_FAILED)


def test_confidence_out_of_range_raises_app_exception():
    exc = _expect_app_exception(VALID_JSON.replace("0.88", "1.8"))

    assert exc.data["errors"][0]["field"] == "confidence"


def test_order_no_none_like_values_normalized():
    for empty_value in ['"null"', '"无"', '""', "null"]:
        raw = VALID_JSON.replace('"10001"', empty_value)
        result = parse_order_intent(raw)
        assert result.order_no is None, f"{empty_value} 应当被归一为 None"


def test_prompt_registered_and_renderable():
    prompt = prompt_registry.get(prompt_id=PROMPT_ID, version=VERSION)

    placeholders = set()
    for message in prompt.messages:
        placeholders |= extract_variables(message.template)

    assert placeholders == set(prompt.required_variables)
    assert prompt.required_variables == ["user_question"]

    messages = render_prompt(
        prompt=prompt, variables={"user_question": "我的快递到哪了？SF123"}
    )
    system_content = messages[0].content

    for intent in OrderIntent:
        assert intent.value in system_content

    assert "只输出一个 JSON 对象" in system_content
    assert '"intent"' in system_content
    assert "{{" not in system_content


def test_schema_rejects_blank_reason():
    try:
        OrderIntentResult.model_validate_json(
            VALID_JSON.replace('"用户要求退款"', '"   "')
        )
    except Exception as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("空白 reason 应当校验失败")


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
