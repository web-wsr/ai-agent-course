import asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.core.config import settings
from app.core.logging import get_logger
from redis.asyncio import Redis

from app.redis.cache import (
    cache_chat_response,
    get_cached_chat_response,
)

from app.repositories.conversation_repository import conversation_repository

from app.schemas.chat import (
    ChatRequest, 
    ChatResponse,
    MessageRole,
    TokenUsage,
    SourceDocument,
)
from app.core.exceptions import AppException, ErrorCode

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


   

    logger.info(
        f"chat_start model={model} message_count={len(request.messages)}"
    )

    if redis:
        cached_answer = await get_cached_chat_response(
            redis=redis,
            question=latest_user_message
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

    


    if "触发业务异常" in latest_user_message:
        raise AppException(
            message="这是一个模拟业务异常",
            code=ErrorCode.LLM_CALL_FAILED,
            status_code=500,
            data={
                "reason": "mock llm failed"
            },
        )

    if "AI Agent" in latest_user_message:
        answer = (
            "AI Agent 可以理解为具备目标理解、任务规划、工具调用和结果反馈能力的智能体"
        )
    elif "RAG" in latest_user_message:
        answer =(
            "RAG 是一种基于知识库的问答系统，通过知识库进行查询，并返回结果给用户,"
            "RAG 的核心是知识库，知识库可以由用户自行构建，也可以通过知识图谱进行自动构建。"
        )
    elif "LangGraph" in latest_user_message:
        answer =(
            "LangGraph 是一个基于知识图谱的问答系统，通过知识图谱进行查询，并返回结果给用户。"
            "LangGraph 的核心是知识图谱，知识图谱可以由用户自行构建，也可以通过知识库进行自动构建。"
        )
    else: 
        answer = f"模拟回答：你问的是【{latest_user_message}】"

    usage = TokenUsage(
        prompt_tokens=count_mock_tokens_from_message(request),
        completion_tokens=len(answer),
        total_tokens=count_mock_tokens_from_message(request) + len(answer)
    )

    if redis:
        await cache_chat_response(
            redis=redis,
            question=latest_user_message,
            answer=answer,
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
            prompt_tokens=usage.prompt_tokens
        )

    logger.info(
        f"chat_success model={model} answer_length={len(answer)}"
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
