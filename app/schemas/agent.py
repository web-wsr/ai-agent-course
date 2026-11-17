from pydantic import BaseModel, Field
from typing import Any
from enum import Enum

class AgentStepType(str, Enum):
    """
    步骤类型
    """
    THINK = "think"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL = "final"

class AgentRunRequest(BaseModel):
    """
    请求参数
    """
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    agent_id: str = Field(..., description="Agent ID")
    stream: bool = Field(default=False, description="是否流式输出")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据") 

class AgentStep(BaseModel):
    step_type: AgentStepType = Field(..., description="步骤类型")
    content: str = Field(..., description="步骤内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="步骤元数据")


class AgentRunResponse(BaseModel):
    """
    响应参数
    """
    answer: str = Field(..., description="最终回答")
    steps: list[AgentStep] = Field(default_factory=list, description="Agent 运行步骤")
    trace_id: str | None = Field(default=None, description="链路追踪 ID")


class AgentInfo(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent 名称")
    description: str = Field(..., description="Agent 描述")


class AgentListResponse(BaseModel):
    agents: list[AgentInfo] = Field(default_factory=list, description="Agent 列表")
    