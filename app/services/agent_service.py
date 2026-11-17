from app.schemas.agent import AgentInfo, AgentListResponse

async def list_agent_service() -> AgentListResponse:
    """
    获取可用的 Agent 列表
    """
    return AgentListResponse(
        agents=[
            AgentInfo(
                agent_id="agent_chat",
                name="通用聊天助手",
                description="用于普通 AI Chat 场景"
            ),
            AgentInfo(
                agent_id="agent_rag",
                name="RAG 检索问答助手",
                description="用于 RAG 检索问答场景"
            )
        ]
    )