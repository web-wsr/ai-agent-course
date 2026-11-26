import asyncio
from contextlib import suppress
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.logging import get_logger
from app.dependencies.llm import get_llm_provider
from app.dependencies.redis import get_redis_client
from app.dependencies.workspace import get_workspace_id
from app.llm.base import BaseLLMProvider
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.schemas.response import ApiResponse
from app.services.rag_service import query_rag
from app.services.rag_stream_service import stream_rag_answer

router = APIRouter()

logger = get_logger(__name__)


@router.post("/rag/query", response_model=ApiResponse[RAGQueryResponse])
async def rag_query(
    request: RAGQueryRequest,
    workspace_id: Annotated[str, Depends(get_workspace_id)],
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> ApiResponse[RAGQueryResponse]:
    """
    RAG 查询接口
    """
    result = await query_rag(request, redis=redis)
    result.trace_id = f"{result.trace_id}_workspace_{workspace_id}"

    return ApiResponse[RAGQueryResponse](data=result)


@router.post("/rag/stream")
async def rag_stream(
    request_body: RAGQueryRequest,
    request: Request,
    workspace_id: Annotated[str, Depends(get_workspace_id)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
):
    """
    RAG 流式问答：事件顺序 source → message* → done / error
    """
    logger.info(
        f"rag_stream_request workspace_id={workspace_id} "
        f"knowledge_base_id={request_body.knowledge_base_id}"
    )

    async def event_generator():
        stream = stream_rag_answer(
            request=request_body,
            llm_provider=llm_provider,
        )

        stop_reason: str | None = None

        try:
            async for event in stream:
                if await request.is_disconnected():
                    stop_reason = "client_disconnected"
                    break

                yield event
        except asyncio.CancelledError:
            stop_reason = "cancelled"
            raise
        finally:
            with anyio.CancelScope(shield=True):
                with suppress(Exception):
                    await stream.aclose()

            if stop_reason:
                logger.info(f"rag_stream_stopped reason={stop_reason}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
