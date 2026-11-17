from typing import Any

from app.schemas.chat import SourceDocument

class KnowledgeRespository:
    async def search_documents(
            self,
            question: str,
            knowledge_base_id: str,
            top_k: int,
            metadata_filter: dict[str, Any] | None = None,
    ) -> list[SourceDocument]:
        return [
            SourceDocument(
                document_id="doc_001",
                title="AI Agent 课程资料",
                content="RAG 是 Retrieval Augmented Generation，用于结合外部知识增强大模型回答。",
                score=0.98,
                metadata={
                    "knowlege_base_id": knowledge_base_id,
                    "page": 1,
                    "filter": metadata_filter or {}
                }
            )
        ][:top_k]

knowledge_repository = KnowledgeRespository()