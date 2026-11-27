import uuid

from app.core.config import settings
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import get_logger

# 大模型
from app.llm.base import BaseLLMProvider
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
from app.services.structured_output_service import structured_output_service
from app.structured_outputs.schemas import IntentClassificationOutput
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# 意图识别命中后的固定话术：不进主模型，直接返回
ASK_ORDER_ID_ANSWER = "请提供订单号，我帮你查询订单进度。"
TRANSFER_HUMAN_ANSWER = "已为你转接人工客服，请稍等，客服会尽快接入。"


def build_intent_gate_answer(intent: IntentClassificationOutput) -> str | None:
    """命中意图规则返回固定话术，未命中返回 None（继续走普通 LLM Chat）。"""
    if intent.intent == "query_order" and intent.need_order_id:
        return ASK_ORDER_ID_ANSWER

    if intent.intent == "human_service":
        return TRANSFER_HUMAN_ANSWER

    return None


async def classify_chat_intent(
    user_message: str,
    model: str,
    llm_provider: BaseLLMProvider,
) -> IntentClassificationOutput | None:
    """回答前先识别意图；识别失败只降级，不阻断主回答流程。"""
    try:
        intent = await structured_output_service.classify_intent(
            user_question=user_message,
            model=model,
            llm_provider=llm_provider,
        )
    except (AppException, LLMProviderError) as exc:
        logger.warning(f"chat_intent_classify_failed error={exc}")
        return None

    logger.info(
        f"chat_intent intent={intent.intent} confidence={intent.confidence} "
        f"need_order_id={intent.need_order_id} strategy={intent.reply_strategy}"
    )

    return intent


async def chat_with_ai(
    request: ChatRequest,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
    llm_provider: BaseLLMProvider | None = None,
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

    provider_name = infer_provider_from_model(request.model)

    # 意图识别在回答之前：query_order 缺订单号 / 需要转人工时直接给固定话术
    if llm_provider is None:
        try:
            llm_provider = LLMProviderFactory.create(provider_name)
        except (LLMProviderError, ValueError) as exc:
            # 创建失败交给下面的主流程统一报错，这里只跳过意图识别
            logger.warning(f"chat_intent_provider_unavailable error={exc}")
            llm_provider = None

    if llm_provider is not None:
        intent = await classify_chat_intent(
            user_message=latest_user_message,
            model=model,
            llm_provider=llm_provider,
        )

        gate_answer = build_intent_gate_answer(intent) if intent else None

        if gate_answer:
            logger.info(f"chat_intent_shortcut intent={intent.intent} model={model}")

            return await respond_with_intent_gate(
                request=request,
                answer=gate_answer,
                model=model,
                user_message=latest_user_message,
                db=db,
                redis=redis,
            )

    llm_request = build_llm_request_from_chat_request(request)

    try:
        llm_provider = llm_provider or LLMProviderFactory.create(provider_name)
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
        await save_chat_messages(
            db=db,
            session_id=request.session_id,
            user_message=latest_user_message,
            answer=answer,
            model=model,
            usage=usage,
        )

    logger.info(
        f"chat_success model={model} answer_length={len(answer)}"
        f"total_tokens={usage.total_tokens}"
    )

    sources = build_mock_sources(latest_user_message)

    return build_chat_response(
        request=request,
        answer=answer,
        model=model,
        usage=usage,
        sources=sources,
        latency_ms=500,
    )


async def respond_with_intent_gate(
    request: ChatRequest,
    answer: str,
    model: str,
    user_message: str,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
) -> ChatResponse:
    """意图命中固定话术：不再调用主模型，直接返回并正常落库 / 写缓存。"""
    usage = TokenUsage()

    if redis:
        await cache_chat_response(
            redis=redis,
            question=user_message,
            answer=answer,
            model=model,
        )

    if db and request.session_id:
        await save_chat_messages(
            db=db,
            session_id=request.session_id,
            user_message=user_message,
            answer=answer,
            model=model,
            usage=usage,
        )

    return build_chat_response(
        request=request,
        answer=answer,
        model=model,
        usage=usage,
        sources=[],
        latency_ms=0,
    )


def build_chat_response(
    request: ChatRequest,
    answer: str,
    model: str,
    usage: TokenUsage,
    sources: list[SourceDocument] | None = None,
    latency_ms: int = 0,
) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        model=model,
        session_id=request.session_id or f"s_{uuid.uuid4().hex[:8]}",
        message_id=f"m_{uuid.uuid4().hex[:8]}",
        usage=usage,
        sources=sources or [],
        trace_id=f"trace_{uuid.uuid4().hex[:8]}",
        latency_ms=latency_ms,
    )


async def save_chat_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    answer: str,
    model: str,
    usage: TokenUsage | None = None,
) -> None:
    """成功回答落库：用户消息 + 助手消息（completed）。"""
    usage = usage or TokenUsage()

    await conversation_repository.add_message(
        db=db,
        conversation_id=session_id,
        role=MessageRole.USER.value,
        content=user_message,
        model=model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )

    await conversation_repository.add_message(
        db=db,
        conversation_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content=answer,
        model=model,
        prompt_tokens=usage.prompt_tokens,
        status=MessageStatus.COMPLETED.value,
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
