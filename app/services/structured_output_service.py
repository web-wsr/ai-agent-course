from app.core.exceptions import AppException, ErrorCode
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMRequest, LLMResponse
from app.prompts.base import PromptScenario
from app.services.prompt_service import prompt_service
from app.structured_outputs.parser import (
    StructuredOutputParseError,
    parse_structured_output,
)
from app.structured_outputs.response_format import (
    build_json_object_response_format,
    build_json_schema_response_format,
)
from app.structured_outputs.retry import parse_or_repair_structured_output
from app.structured_outputs.schemas import (
    AgentPlanOutput,
    IntentClassificationOutput,
    OrderInfoExtractOutput,
    RAGStructuredAnswerOutput,
)
from pydantic import BaseModel

logger = get_logger(__name__)

# 只有“报错提到 response_format / json_schema + 不支持”才判定为模型不支持，
# 避免把鉴权失败、参数写错这类 400 也当成不支持而静默降级。
_SCHEMA_ERROR_HINTS = ("response_format", "json_schema", "json schema")
_UNSUPPORTED_ERROR_HINTS = (
    "unsupported",
    "not support",
    "does not support",
    "unknown parameter",
    "invalid_value",
    "invalid value",
)
_SCHEMA_UNSUPPORTED_STATUS_CODES = {400, 404, 422, 501}


def is_json_schema_unsupported(exc: LLMProviderError) -> bool:
    """判断异常是不是“当前模型不支持 json_schema 输出”。"""
    if (
        exc.status_code is not None
        and exc.status_code not in _SCHEMA_UNSUPPORTED_STATUS_CODES
    ):
        return False

    text = f"{exc.message} {exc.raw_error or ''}".lower()

    return any(hint in text for hint in _SCHEMA_ERROR_HINTS) and any(
        hint in text for hint in _UNSUPPORTED_ERROR_HINTS
    )


class StructuredOutputService:
    @staticmethod
    def _build_response_format(
        schema: type[BaseModel],
        name: str,
        use_json_schema: bool,
    ) -> dict:
        if use_json_schema:
            return build_json_schema_response_format(schema=schema, name=name)

        return build_json_object_response_format()

    async def classify_intent(
        self,
        user_question: str,
        model: str,
        llm_provider: BaseLLMProvider,
        use_json_schema: bool = False,
    ) -> IntentClassificationOutput:
        messages = prompt_service.render_by_prompt_id(
            prompt_id="intent_classification_structured",
            variables={
                "user_question": user_question,
            },
        )

        request = LLMRequest(
            model=model,
            messages=messages,
            temperature=0.1,
            stream=False,
            response_format=self._build_response_format(
                schema=IntentClassificationOutput,
                name="intent_classification",
                use_json_schema=use_json_schema,
            ),
        )

        return await self._call_and_parse(
            request=request,
            llm_provider=llm_provider,
            schema=IntentClassificationOutput,
            task_name="intent_classification",
            use_json_schema=use_json_schema,
        )

    async def generate_rag_answer(
        self,
        user_question: str,
        retrieved_context: str,
        model: str,
        llm_provider: BaseLLMProvider,
        use_json_schema: bool = False,
    ) -> RAGStructuredAnswerOutput:
        messages = prompt_service.render_by_prompt_id(
            prompt_id="rag_structured_answer",
            variables={
                "user_question": user_question,
                "retrieved_context": retrieved_context,
            },
        )

        request = LLMRequest(
            model=model,
            messages=messages,
            temperature=0.1,
            stream=False,
            response_format=self._build_response_format(
                schema=RAGStructuredAnswerOutput,
                name="rag_structured_answer",
                use_json_schema=use_json_schema,
            ),
        )

        return await self._call_and_parse(
            request=request,
            llm_provider=llm_provider,
            schema=RAGStructuredAnswerOutput,
            task_name="rag_structured_answer",
            use_json_schema=use_json_schema,
        )

    async def plan_agent_task(
        self,
        user_goal: str,
        available_tools: list[str],
        constraints: str,
        model: str,
        llm_provider: BaseLLMProvider,
        use_json_schema: bool = False,
    ) -> AgentPlanOutput:
        messages = prompt_service.render_by_prompt_id(
            prompt_id="agent_plan_structured",
            variables={
                "user_goal": user_goal,
                "available_tools": available_tools,
                "constraints": constraints,
            },
        )

        request = LLMRequest(
            model=model,
            messages=messages,
            temperature=0.1,
            stream=False,
            response_format=self._build_response_format(
                schema=AgentPlanOutput,
                name="agent_plan",
                use_json_schema=use_json_schema,
            ),
        )

        return await self._call_and_parse(
            request=request,
            llm_provider=llm_provider,
            schema=AgentPlanOutput,
            task_name="agent_plan",
            use_json_schema=use_json_schema,
        )

    async def extract_order_info(
        self,
        user_question: str,
        model: str,
        llm_provider: BaseLLMProvider,
        use_json_schema: bool = False,
    ) -> OrderInfoExtractOutput:
        """从用户话术中抽取订单号 / 手机号后四位，判断信息是否齐全。"""
        messages = prompt_service.render_by_prompt_id(
            prompt_id="order_info_extract_structured",
            variables={
                "user_question": user_question,
            },
        )

        request = LLMRequest(
            model=model,
            messages=messages,
            temperature=0.1,
            stream=False,
            response_format=self._build_response_format(
                schema=OrderInfoExtractOutput,
                name="order_info_extract",
                use_json_schema=use_json_schema,
            ),
        )

        return await self._call_and_parse(
            request=request,
            llm_provider=llm_provider,
            schema=OrderInfoExtractOutput,
            task_name="order_info_extract",
            use_json_schema=use_json_schema,
        )

    async def _call_and_parse(
        self,
        request: LLMRequest,
        llm_provider: BaseLLMProvider,
        schema: type[BaseModel],
        task_name: str,
        use_json_schema: bool = False,
    ):
        logger.info(
            f"structured_output_start task={task_name} "
            f"model={request.model} schema={schema.__name__} "
            f"use_json_schema={use_json_schema}"
        )

        try:
            response = await self._chat_with_format_fallback(
                request=request,
                llm_provider=llm_provider,
                task_name=task_name,
                use_json_schema=use_json_schema,
            )

        except LLMProviderError as exc:
            logger.exception(
                f"structured_output_llm_error task={task_name} "
                f"provider={exc.provider} status_code={exc.status_code}"
            )

            raise AppException(
                message="结构化输出模型调用失败",
                code=ErrorCode.LLM_CALL_FAILED,
                status_code=500,
                data={
                    "task": task_name,
                    "provider": exc.provider,
                    "status_code": exc.status_code,
                },
            ) from exc

        try:
            # result = parse_structured_output(
            #     raw_text=response.content,
            #     schema=schema,
            # )
            result = await parse_or_repair_structured_output(
                raw_text=response.content,
                schema=schema,
                model=request.model,
                llm_provider=llm_provider,
            )

        except StructuredOutputParseError as exc:
            logger.warning(
                f"structured_output_parse_failed task={task_name} detail={exc.detail}"
            )

            raise AppException(
                message="模型结构化输出解析失败",
                code=ErrorCode.LLM_RESPONSE_PARSE_FAILED,
                status_code=500,
                data={
                    "task": task_name,
                    "detail": exc.detail,
                },
            ) from exc
        logger.info(
            f"structured_output_success task={task_name} schema={schema.__name__}"
        )

        return result

    async def _chat_with_format_fallback(
        self,
        request: LLMRequest,
        llm_provider: BaseLLMProvider,
        task_name: str,
        use_json_schema: bool,
    ) -> LLMResponse:
        """json_schema 不受支持时，自动降级成 json_object 再请求一次。"""
        try:
            return await llm_provider.chat(request)

        except LLMProviderError as exc:
            if not (use_json_schema and is_json_schema_unsupported(exc)):
                raise

            logger.warning(
                f"structured_output_json_schema_fallback task={task_name} "
                f"provider={exc.provider} status_code={exc.status_code} "
                f"reason={(exc.raw_error or exc.message)[:200]}"
            )

            fallback_request = request.model_copy(
                update={"response_format": build_json_object_response_format()}
            )

            return await llm_provider.chat(fallback_request)


structured_output_service = StructuredOutputService()
