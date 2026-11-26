import uuid

from app.core.config import settings
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import get_logger

# 大模型
from app.llm.errors import LLMProviderError
from app.llm.factory import LLMProviderFactory, infer_provider_from_model
from app.llm.schemas import LLMMessage, LLMRequest, LLMRole
from app.prompts.base import PromptScenario
from app.redis.cache import (
    cache_chat_response,
    get_cached_chat_response,
)
from app.repositories.conversation_repository import conversation_repository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageRole,
    MessageStatus,
    SourceDocument,
    TokenUsage,
)
from app.services.prompt_service import prompt_service
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def chat_with_ai(
    request: ChatRequest,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
) -> ChatResponse:
    # await asyncio.sleep(1)
    # 支持的模型
    # support_models = ["deepseek-chat", "qwen-plus", "gpt-4o-mini"]
    # if request.model not in support_models:
    #     raise HTTPException(
    #         status_code=400,
    #         detail=f"模型{request.model}不存在"
    #     )
    # return ChatResponse(
    #     answer=f"AI 模拟回答：你问的是【{request.message}】",
    #     model=request.model,
    # )
    latest_user_message = get_latest_user_message(request)
    model = request.model or settings.default_model

    logger.info(f"chat_start model={model} message_count={len(request.messages)}")

    if redis:
        cached_answer = await get_cached_chat_response(
            redis=redis, question=latest_user_message, model=model
        )

        if cached_answer:
            logger.info("chat_response_cache_hit")

            return ChatResponse(
                answer=cached_answer,
                model=model,
                session_id=request.session_id,
                message_id=f"m_{uuid.uuid4().hex[:8]}",
                usage=TokenUsage(),
                sources=[],
                trace_id=f"trace_{uuid.uuid4().hex[:8]}",
            )

    # if "触发业务异常" in latest_user_message:
    #     raise AppException(
    #         message="这是一个模拟业务异常",
    #         code=ErrorCode.LLM_CALL_FAILED,
    #         status_code=500,
    #         data={"reason": "mock llm failed"},
    #     )

    # if "AI Agent" in latest_user_message:
    #     answer = (
    #         "AI Agent 可以理解为具备目标理解、任务规划、工具调用和结果反馈能力的智能体"
    #     )
    # elif "RAG" in latest_user_message:
    #     answer = (
    #         "RAG 是一种基于知识库的问答系统，通过知识库进行查询，并返回结果给用户,"
    #         "RAG 的核心是知识库，知识库可以由用户自行构建，也可以通过知识图谱进行自动构建。"
    #     )
    # elif "LangGraph" in latest_user_message:
    #     answer = (
    #         "LangGraph 是一个基于知识图谱的问答系统，通过知识图谱进行查询，并返回结果给用户。"
    #         "LangGraph 的核心是知识图谱，知识图谱可以由用户自行构建，也可以通过知识库进行自动构建。"
    #     )
    # else:
    #     answer = f"模拟回答：你问的是【{latest_user_message}】"

    provider_name = infer_provider_from_model(request.model)
    llm_request = build_llm_request_from_chat_request(request)

    try:
        llm_provider = LLMProviderFactory.create(provider_name)
        llm_response = await llm_provider.chat(llm_request)
    except LLMProviderError as exc:
        logger.exception(
            f"chat_llm_provider_error provider={exc.provider}"
            f"status_code={exc.status_code}"
        )

        # 异常也要留痕：保存一条 status=failed 的记录，便于排查
        if db and request.session_id:
            await save_failed_messages(
                db=db,
                session_id=request.session_id,
                user_message=latest_user_message,
                model=request.model,
            )

        raise AppException(
            message=exc.message,
            code=ErrorCode.LLM_CALL_FAILED,
            status_code=500,
            data={
                "provider": exc.provider,
                "status_code": exc.status_code,
            },
        ) from exc

    answer = llm_response.content

    usage = TokenUsage(
        prompt_tokens=llm_response.usage.prompt_tokens,
        completion_tokens=llm_response.usage.completion_tokens,
        total_tokens=llm_response.usage.total_tokens,
    )

    if redis:
        await cache_chat_response(
            redis=redis,
            question=latest_user_message,
            answer=answer,
            model=model,
        )

    if db and request.session_id:
        await conversation_repository.add_message(
            db=db,
            conversation_id=request.session_id,
            role=MessageRole.USER.value,
            content=latest_user_message,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

        await conversation_repository.add_message(
            db=db,
            conversation_id=request.session_id,
            role=MessageRole.ASSISTANT.value,
            content=answer,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            status=MessageStatus.COMPLETED.value,
        )

    logger.info(
        f"chat_success model={model} answer_length={len(answer)}"
        f"total_tokens={usage.total_tokens}"
    )

    sources = build_mock_sources(latest_user_message)

    return ChatResponse(
        answer=answer,
        model=model,
        session_id=request.session_id or f"s_{uuid.uuid4().hex[:8]}",
        message_id=f"m_{uuid.uuid4().hex[:8]}",
        usage=usage,
        sources=sources,
        trace_id=f"trace_{uuid.uuid4().hex[:8]}",
        latency_ms=500,
    )


async def save_failed_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    model: str,
) -> None:
    """调用模型失败时落库：用户消息正常记录，助手消息标 failed。"""
    try:
        await conversation_repository.add_message(
            db=db,
            conversation_id=session_id,
            role=MessageRole.USER.value,
            content=user_message,
            model=model,
        )

        await conversation_repository.add_message(
            db=db,
            conversation_id=session_id,
            role=MessageRole.ASSISTANT.value,
            content="",
            model=model,
            status=MessageStatus.FAILED.value,
        )
    except Exception:
        # 落库失败不能盖住原始的 LLM 异常
        logger.exception("chat_save_failed_messages_error")


def get_latest_user_message(request: ChatRequest) -> str:
    for msg in reversed(request.messages):
        if msg.role == MessageRole.USER:
            return msg.content

    return request.messages[-1].content


def count_mock_tokens_from_message(request: ChatRequest) -> int:
    return sum(len(msg.content) for msg in request.messages)


def build_mock_sources(question: str) -> list[SourceDocument]:
    if "RAG" not in question and "知识库" not in question:
        return []

    return [
        SourceDocument(
            document_id="doc_001",
            title="企业知识库说明文档",
            content="RAG 是 Retrieval Augmented Generation，用于结合外部知识增强大模型回答。",
            score=0.89,
            metadata={
                "source": "mock",
                "page": 1,
            },
        )
    ]


def build_llm_request_from_chat_request(request: ChatRequest) -> LLMRequest:
    return LLMRequest(
        model=request.model,
        messages=build_prompt_messages_for_chat(request),
        temperature=request.temperature,
        stream=request.stream,
    )


def build_prompt_messages_for_chat(request: ChatRequest) -> list[LLMMessage]:
    has_system_message = any(
        message.role == MessageRole.SYSTEM for message in request.messages
    )
    # prompt 版本
    version = request.prompt_version or "v1"

    if has_system_message:
        return [
            LLMMessage(
                role=LLMRole(message.role.value),
                content=message.content,
            )
            for message in request.messages
        ]

    latest_user_message = get_latest_user_message(request)

    # 电商客服prompt 场景
    if request.prompt_scenario == PromptScenario.ECOMMERCE_CUSTOMER_SERVICE.value:
        return prompt_service.render_by_scenario(
            scenario=PromptScenario.ECOMMERCE_CUSTOMER_SERVICE,
            version=version,
            variables={
                "user_question": latest_user_message,
                "business_rules": request.metadata.get(
                    "business_rules",
                    "暂无额外业务规则。",
                ),
                "order_info": request.metadata.get(
                    "order_info",
                    "用户未提供订单信息。",
                ),
            },
        )

    return prompt_service.render_by_scenario(
        scenario=PromptScenario.GENERAL_CHAT,
        variables={
            "user_question": latest_user_message,
        },
    )
