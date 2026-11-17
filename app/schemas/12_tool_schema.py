from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AgentStepType(str, Enum):
    """Agent 步骤类型"""

    THINK = "think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL = "final"

class AgentStep(BaseModel):
    """Agent 步骤"""

    step_type: AgentStepType = Field(..., description="步骤类型")
    content: str = Field(..., description="步骤内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展信息")

class AgentState(BaseModel):
    """Agent 状态"""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., description="用户ID")
    session_id: str = Field(..., alias="sessionId", description="会话ID")
    question: str = Field(..., min_length=1, description="问题")
    steps: list[AgentStep] = Field(default_factory=list, description="Agent 执行步骤列表")
    final_answer: str | None = Field(default=None, description="最终答案")

state = AgentState(
    user_id="u_001",
    session_id="s_001",
    question="帮我查询订单号 12345678 的物流信息"
)

state.steps.append(
    AgentStep(
        step_type=AgentStepType.THINK,
        content="用户想要查询订单物流信息, 需要调用 query_logistics 工具"
    )
)

state.steps.append(
    AgentStep(
        step_type=AgentStepType.TOOL_CALL,
        content="调用 query_logistics",
        metadata={
            "order_id": "12345678"
        }
    )
)

state.final_answer = "物流信息如下：订单号 12345678 的物流信息为：正在配送，预计明天送达"

print(state.model_dump())