from typing import Any
 
from pydantic import BaseModel, Field
from app.schemas.chat import SourceDocument, TokenUsage


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,description="用户问题")
    knowledge_base_id: str = Field(..., description="知识库 ID")
    top_k: int = Field(default=5, ge=1, le=20, description="返回文档数量")
    rerank: bool = Field(default=True, description="是否进行文档重新排序")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

class RAGQueryResponse(BaseModel):
    answer: str = Field(..., description="AI 回答")
    knowledge_base_id: str = Field(..., description="知识库 ID")
    sources: list[SourceDocument] = Field(default_factory=list, description="引用来源")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 用量")
    trace_id: str | None = Field(default=None, description="链路追踪 ID")