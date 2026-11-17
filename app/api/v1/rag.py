from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.dependencies.redis import get_redis_client
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.schemas.response import ApiResponse
from app.services.rag_service import query_rag

from app.dependencies.workspace import get_workspace_id

router = APIRouter()

@router.post("/rag/query", response_model=ApiResponse[RAGQueryResponse])
async def rag_query(
    request: RAGQueryRequest,
    workspace_id: str = Depends(get_workspace_id),
    redis: Redis = Depends(get_redis_client),
) -> ApiResponse[RAGQueryResponse]:
    """
    RAG 查询接口
    """
    result = await query_rag(request, redis=redis)
    result.trace_id = f"{result.trace_id}_workspace_{workspace_id}"
    
    return ApiResponse[RAGQueryResponse](data=result)
