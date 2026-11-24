# 订单意图识别服务：调用模型 -> 解析 JSON -> Pydantic 校验 -> 失败抛 AppException

import re

from app.core.config import settings
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.factory import LLMProviderFactory
from app.llm.schemas import LLMRequest
from app.prompts.registry import prompt_registry
from app.prompts.renderer import render_prompt
from app.schemas.order_intent import OrderIntentResult
from pydantic import ValidationError

logger = get_logger(__name__)

PROMPT_ID = "order_intent"
PROMPT_VERSION = "v1"

_CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def strip_code_fence(raw_output: str) -> str:
    """去掉模型偶尔带上的 ```json 代码块包裹。"""
    return _CODE_FENCE_PATTERN.sub("", raw_output.strip())


def extract_json_text(raw_output: str) -> str:
    """从模型输出里截取第一个 JSON 对象，兼容前后多说了几句话的情况。"""
    text = strip_code_fence(raw_output)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        return text

    return text[start : end + 1]


def parse_order_intent(raw_output: str) -> OrderIntentResult:
    """把模型原始文本转成 OrderIntentResult，校验不过就抛 AppException。"""
    text = extract_json_text(raw_output)

    try:
        return OrderIntentResult.model_validate_json(text)
    except ValidationError as exc:
        logger.warning(
            f"order_intent_validate_failed raw_output={raw_output[:200]} "
            f"errors={exc.error_count()}"
        )

        raise AppException(
            message="意图识别结果校验失败",
            code=ErrorCode.LLM_RESPONSE_PARSE_FAILED,
            status_code=500,
            data={
                "raw_output": raw_output[:500],
                "errors": [
                    {
                        "field": ".".join(str(item) for item in error["loc"]),
                        "message": error["msg"],
                    }
                    for error in exc.errors(include_url=False)
                ],
            },
        ) from exc


async def classify_order_intent(
    user_question: str,
    model: str | None = None,
    provider: BaseLLMProvider | None = None,
) -> OrderIntentResult:
    """识别用户问题的订单意图。"""
    prompt = prompt_registry.get(prompt_id=PROMPT_ID, version=PROMPT_VERSION)
    messages = render_prompt(prompt=prompt, variables={"user_question": user_question})

    llm_provider = provider or LLMProviderFactory.create()
    response = await llm_provider.chat(
        LLMRequest(
            model=model or settings.default_model,
            messages=messages,
            temperature=0,
            stream=False,
        )
    )

    result = parse_order_intent(response.content)

    logger.info(
        f"order_intent_done intent={result.intent.value} "
        f"confidence={result.confidence} need_human={result.need_human}"
    )

    return result
