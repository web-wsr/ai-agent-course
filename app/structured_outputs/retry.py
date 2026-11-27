# 实现结构化输出修复 Prompt（支持循环重试）
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AppException, ErrorCode
from app.llm.base import BaseLLMProvider
from app.llm.schemas import LLMMessage, LLMRequest, LLMRole
from app.structured_outputs.parser import (
    StructuredOutputParseError,
    parse_structured_output,
)
from app.structured_outputs.response_format import (
    build_json_object_response_format,
)

REPAIR_SYSTEM_PROMPT = (
    "你是一个 JSON 修复器。\n"
    "你的任务是把输入内容修复为符合目标结构的合法 JSON。\n"
    "只能输出 JSON，不要输出 Markdown，不要输出解释。"
)


def _build_repair_messages(
    raw_text: str,
    schema: type[BaseModel],
    error: StructuredOutputParseError,
) -> list[LLMMessage]:
    return [
        LLMMessage(
            role=LLMRole.SYSTEM,
            content=REPAIR_SYSTEM_PROMPT,
        ),
        LLMMessage(
            role=LLMRole.USER,
            content=(
                "目标 JSON Schema：\n"
                f"{schema.model_json_schema()}\n"
                "\n"
                "上一次输出：\n"
                f"{raw_text}\n"
                "\n"
                "解析错误：\n"
                f"{error.detail}\n"
                "\n"
                "请修复为合法 JSON。"
            ),
        ),
    ]


async def _request_repair(
    raw_text: str,
    schema: type[BaseModel],
    error: StructuredOutputParseError,
    model: str,
    llm_provider: BaseLLMProvider,
) -> str:
    """发起一次修复请求，返回模型修复后的文本。"""
    repair_request = LLMRequest(
        model=model,
        messages=_build_repair_messages(
            raw_text=raw_text,
            schema=schema,
            error=error,
        ),
        temperature=0,
        stream=False,
        response_format=build_json_object_response_format(),
    )

    repair_response = await llm_provider.chat(repair_request)

    return repair_response.content


async def parse_or_repair_structured_output(
    raw_text: str,
    schema: type[BaseModel],
    model: str,
    llm_provider: BaseLLMProvider,
    max_retries: int | None = None,
) -> BaseModel:
    """
    解析结构化输出，失败时循环修复重试。

    首次解析不消耗重试次数，之后最多发起 max_retries 次修复请求；
    仍未通过校验则抛出 AppException。max_retries 为空时取配置项。
    """
    retry_limit = (
        settings.structured_output_max_retries if max_retries is None else max_retries
    )
    retry_limit = max(int(retry_limit), 0)

    current_text = raw_text
    last_error: StructuredOutputParseError | None = None

    for attempt in range(retry_limit + 1):
        try:
            return parse_structured_output(
                raw_text=current_text,
                schema=schema,
            )

        except StructuredOutputParseError as exc:
            last_error = exc

            if attempt >= retry_limit:
                break

            current_text = await _request_repair(
                raw_text=current_text,
                schema=schema,
                error=exc,
                model=model,
                llm_provider=llm_provider,
            )

    raise AppException(
        message=f"结构化输出修复 {retry_limit} 次后仍不合法：{schema.__name__}",
        code=ErrorCode.STRUCTURED_OUTPUT_PARSE_FAILED,
        status_code=500,
        data={
            "schema": schema.__name__,
            "max_retries": retry_limit,
            "attempts": retry_limit + 1,
            "detail": last_error.detail if last_error else None,
        },
    ) from last_error
