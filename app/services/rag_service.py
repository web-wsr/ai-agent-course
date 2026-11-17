import uuid

from app.core.exceptions import AppException, ErrorCode
from app.core.logging import get_logger
from app.redis.cache import cache_rag_result, get_cached_rag_result
from app.repositories.knowledge_repository import knowledge_repository
from app.schemas.chat import SourceDocument, TokenUsage
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from redis.asyncio import Redis

logger = get_logger(__name__)


async def query_rag(
    request: RAGQueryRequest,
    redis: Redis | None = None,
) -> RAGQueryResponse:
    # source = SourceDocument(
    #     document_id="doc_001",
    #     title="AI Agent 课程资料",
    #     content="RAG 是检索增强生成，用于让大模型结合外部知识回答问题",
    #     score=0.98,
    #     metadata={
    #         "knowledge_base_id": request.knowledge_base_id,
    #         "page": 1,
    #     },
    # )

    logger.info(
        f"rag_query_start knowledge_base_id={request.knowledge_base_id} top_k={request.top_k}"
    )

    if redis is not None:
        cached_result = await get_cached_rag_result(redis=redis, request=request)
        if cached_result is not None:
            logger.info("rag_query_cache_hit")
            cached_result.trace_id = f"trace_{uuid.uuid4().hex[:8]}"
            return cached_result
        logger.info("rag_query_cache_miss")

    if request.knowledge_base_id == "kb_error":
        raise AppException(
            messgae="知识库查询失败",
            code=ErrorCode.RAG_QUERY_FAILED,
            status_code=500,
            data={"knowledge_base_id": request.knowledge_base_id},
        )

    sources = await knowledge_repository.search_documents(
        question=request.question,
        knowledge_base_id=request.knowledge_base_id,
        top_k=request.top_k,
        metadata_filter=request.metadata,
    )

    answer = f"根据知识库 {request.knowledge_base_id} 的内容，RAG 是检索增强生成。"

    result = RAGQueryResponse(
        answer=answer,
        knowledge_base_id=request.knowledge_base_id,
        sources=sources,
        usage=TokenUsage(
            prompt_tokens=len(request.question),
            completion_tokens=len(answer),
            total_tokens=len(request.question) + len(answer),
        ),
        trace_id=f"trace_{uuid.uuid4().hex[:8]}",
    )

    if redis is not None:
        await cache_rag_result(redis=redis, request=request, result=result)

    return result
