import asyncio
import uuid
from collections.abc import AsyncGenerator

import anyio

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMRequest
from app.redis.cache import cache_chat_response, get_cached_chat_response
from app.repositories.conversation_repository import conversation_repository
from app.schemas.chat import ChatRequest, MessageRole, MessageStatus, TokenUsage
from app.services.chat_service import (
    build_llm_request_from_chat_request,
    get_latest_user_message,
)
from app.utils.sse import (
    format_done_event,
    format_error_event,
    format_sse,
    format_thinking_event,
)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def stream_chat_with_ai(
    request: ChatRequest,
    llm_provider: BaseLLMProvider,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
) -> AsyncGenerator[str, None]:
    latest_user_message = get_latest_user_message(request)

    llm_request: LLMRequest = build_llm_request_from_chat_request(request)
    llm_request.stream = True

    message_id = f"m_{uuid.uuid4().hex[:8]}"
    full_answer = ""
    final_usage = TokenUsage()

    logger.info(
        f"chat_stream_start model={llm_request.model} "
        f"message_count={len(llm_request.messages)}"
    )
    # 增加缓存命中的逻辑
    if redis:
        cached_answer = await get_cached_chat_response(
            redis=redis,
            question=latest_user_message,
            model=llm_request.model,
        )

        if cached_answer:
            logger.info("chat_response_cache_hit")
            yield format_sse(
                event="start",
                data={
                    "message_id": message_id,
                    "model": llm_request.model,
                    "session_id": request.session_id,
                    "cache_hit": True,
                },
            )

            for part in split_text(cached_answer, size=8):
                yield format_sse(
                    event="message",
                    data={
                        "content": part,
                        "message_id": message_id,
                        "cache_hit": True,
                    },
                )

            yield format_done_event(
                {
                    "message_id": message_id,
                    "finish_reason": "cache_hit",
                    "usage": final_usage.model_dump(),
                }
            )

            return

    # 流式一开始先发 thinking：前端展示灰色提示，等首个 message 到了再隐藏。
    # 缓存命中不走模型，直接吐正文，所以不发 thinking，避免提示一闪而过。
    yield format_thinking_event(message_id=message_id)

    yield format_sse(
        event="start",
        data={
            "message_id": message_id,
            "model": llm_request.model,
            "session_id": request.session_id,
        },
    )

    # 默认按正常结束处理，异常/中断时在下面改写
    status = MessageStatus.COMPLETED

    try:
        async for chunk in llm_provider.stream_chat(llm_request):
            if chunk.content:
                full_answer += chunk.content

                yield format_sse(
                    event="message",
                    data={
                        "content": chunk.content,
                        "message_id": message_id,
                    },
                )

            if chunk.usage:
                final_usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )

        logger.info(
            f"chat_stream_success model={llm_request.model} "
            f"answer_length={len(full_answer)} "
            f"total_tokens={final_usage.total_tokens}"
        )

        # 写入缓存会话结果
        if redis and full_answer:
            await cache_chat_response(
                redis=redis,
                question=latest_user_message,
                answer=full_answer,
                model=llm_request.model,
            )

        yield format_done_event(
            {
                "message_id": message_id,
                "finish_reason": "stop",
                "usage": final_usage.model_dump(),
            }
        )

    except (GeneratorExit, asyncio.CancelledError):
        # 用户点停止 / 连接断开：已经生成的部分标成 interrupted 落库
        status = MessageStatus.INTERRUPTED
        logger.info(
            f"chat_stream_interrupted model={llm_request.model} "
            f"answer_length={len(full_answer)}"
        )
        raise

    except LLMProviderError as exc:
        status = MessageStatus.FAILED
        logger.exception(
            f"chat_stream_llm_error provider={exc.provider} "
            f"status_code={exc.status_code}"
        )

        yield format_error_event(
            message=exc.message,
            code=int(ErrorCode.LLM_CALL_FAILED),
            data={
                "provider": exc.provider,
                "status_code": exc.status_code,
            },
        )

    except Exception as exc:
        status = MessageStatus.FAILED
        logger.exception(f"chat_stream_unhandled_error error={repr(exc)}")

        yield format_error_event(
            message="流式输出失败",
            code=int(ErrorCode.INTERNAL_ERROR),
        )

    finally:
        # 统一落库：completed / failed / interrupted 都在这里写，
        # 保证无论正常结束、异常还是用户中断，都有一条带状态的记录。
        if db and request.session_id:
            try:
                with anyio.CancelScope(shield=True):
                    await save_stream_messages(
                        db=db,
                        session_id=request.session_id,
                        user_message=latest_user_message,
                        assistant_message=full_answer,
                        model=llm_request.model,
                        usage=final_usage,
                        status=status,
                    )
            except Exception:
                logger.exception("chat_stream_save_message_failed")


async def save_stream_messages(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    assistant_message: str,
    model: str,
    usage: TokenUsage,
    status: MessageStatus = MessageStatus.COMPLETED,
):
    await conversation_repository.add_message(
        db=db,
        conversation_id=session_id,
        role=MessageRole.USER.value,
        content=user_message,
        model=model,
        prompt_tokens=usage.prompt_tokens,
    )

    await conversation_repository.add_message(
        db=db,
        conversation_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content=assistant_message,
        model=model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        status=status.value,
    )


def split_text(text: str, size: int = 8) -> list[str]:
    """
    将文本分割成指定长度的子串
    """
    return [text[i : i + size] for i in range(0, len(text), size)]
