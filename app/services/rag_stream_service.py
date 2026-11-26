# RAG 流式问答：先 source，再 message，最后 done / error

import uuid

from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMProviderError
from app.llm.schemas import LLMRequest
from app.prompts.registry import prompt_registry
from app.prompts.renderer import render_prompt
from app.repositories.knowledge_repository import knowledge_repository
from app.schemas.chat import SourceDocument, TokenUsage
from app.schemas.rag import RAGQueryRequest
from app.utils.sse import format_done_event, format_error_event, format_sse

logger = get_logger(__name__)

RAG_PROMPT_ID = "rag_qa"
RAG_PROMPT_VERSION = "v2"  # v2 强制引用编号，正好配合 source 事件

# 没有检索到任何片段时的兜底回答，不走模型
NO_SOURCE_ANSWER = "知识库中暂未找到相关信息。"


def build_retrieved_context(sources: list[SourceDocument]) -> str:
    """把检索结果拼成带编号的上下文，编号要和 source 事件的 index 对齐。"""
    return "\n".join(
        f"[{index}] {source.title}：{source.content}"
        for index, source in enumerate(sources, start=1)
    )


def build_source_event(index: int, source: SourceDocument) -> str:
    return format_sse(
        event="source",
        data={
            "index": index,  # 与回答里的 [n] 对应
            "document_id": source.document_id,
            "title": source.title,
            "score": source.score,
        },
    )


async def stream_rag_answer(
    request: RAGQueryRequest,
    llm_provider: BaseLLMProvider,
    model: str | None = None,
):
    """RAG 流式回答：检索 -> source* -> message* -> done。"""
    message_id = f"m_{uuid.uuid4().hex[:8]}"
    final_usage = TokenUsage()
    full_answer = ""

    logger.info(
        f"rag_stream_start knowledge_base_id={request.knowledge_base_id} "
        f"top_k={request.top_k}"
    )

    try:
        sources = await knowledge_repository.search_documents(
            question=request.question,
            knowledge_base_id=request.knowledge_base_id,
            top_k=request.top_k,
            metadata_filter=request.metadata,
        )

        # 1. 先发 source，让前端在正文出现前就能渲染引用卡片
        for index, source in enumerate(sources, start=1):
            yield build_source_event(index, source)

        # 2. 没有检索结果就不调模型，省一次调用，也避免模型瞎编
        if not sources:
            logger.info("rag_stream_no_source")
            yield format_sse(
                event="message",
                data={"content": NO_SOURCE_ANSWER, "message_id": message_id},
            )
            yield format_done_event(
                {
                    "message_id": message_id,
                    "finish_reason": "no_source",
                    "usage": final_usage.model_dump(),
                    "source_count": 0,
                }
            )
            return

        # 3. 用检索结果渲染 RAG prompt（v2 要求每个结论带 [n]）
        prompt = prompt_registry.get(
            prompt_id=RAG_PROMPT_ID, version=RAG_PROMPT_VERSION
        )
        messages = render_prompt(
            prompt=prompt,
            variables={
                "user_question": request.question,
                "retrieved_context": build_retrieved_context(sources),
            },
        )

        llm_request = LLMRequest(
            model=model or settings.default_model,
            messages=messages,
            temperature=0.3,
            stream=True,
        )

        # 4. 流式输出正文
        async for chunk in llm_provider.stream_chat(llm_request):
            if chunk.content:
                full_answer += chunk.content

                yield format_sse(
                    event="message",
                    data={"content": chunk.content, "message_id": message_id},
                )

            if chunk.usage:
                final_usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )

        logger.info(
            f"rag_stream_success source_count={len(sources)} "
            f"answer_length={len(full_answer)}"
        )

        # 5. 结束
        yield format_done_event(
            {
                "message_id": message_id,
                "finish_reason": "stop",
                "usage": final_usage.model_dump(),
                "source_count": len(sources),
            }
        )

    except LLMProviderError as exc:
        logger.exception(
            f"rag_stream_llm_error provider={exc.provider} "
            f"status_code={exc.status_code}"
        )

        yield format_error_event(
            message=exc.message,
            code=int(ErrorCode.RAG_QUERY_FAILED),
            data={"provider": exc.provider, "status_code": exc.status_code},
        )

    except Exception as exc:
        logger.exception(f"rag_stream_unhandled_error error={repr(exc)}")

        yield format_error_event(
            message="RAG 流式输出失败",
            code=int(ErrorCode.RAG_QUERY_FAILED),
        )
