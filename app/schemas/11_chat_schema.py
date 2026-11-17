from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ChatMessage(BaseModel):
    role: MessageRole = Field(..., description="消息的角色，例如 'user' 或 'assistant'")
    content: str = Field(..., min_length=1, description="消息的内容")

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(..., min_length=1, description="对话消息列表")
    model: str = Field(default="deepseek-chat", description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=1, description="生成文本的随机性")
    stream: bool = Field(default=True, description="是否启用流式输出")
    session_id: str | None = Field(default=None, alias="sessionId", description="会话ID")

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        supported_models = ["deepseek-chat", "glm-5.2", "gpt-3.5-turbo"]
        if value not in supported_models:
            raise ValueError(f"模型{value}不存在")
        return value

class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI生成的回答")
    model: str = Field(..., description="使用的模型名称")
    session_id: str | None = Field(default=None, alias="sessionId", description="会话ID")

request = ChatRequest(
    messages= [
        ChatMessage(role=MessageRole.SYSTEM, content="你是一个AI助手"),
        ChatMessage(role=MessageRole.USER, content="你好")
    ],
    model="deepseek-chat",
    temperature=0.5,
)

response = ChatResponse(
    answer="你好, 我是一个AI助手",
    model="deepseek-chat",
    session_id=request.session_id,
)

print(response.model_dump())
print(request.model_dump(exclude_none=True))