from pydantic import BaseModel, Field
from enum import Enum

# class UserCreateRequest(BaseModel):
#     name: str = Field(..., min_length=2, max_length=10)
#     email: str | None= None
#     age: int = Field(...,ge=0, le=120)

# user = UserCreateRequest(
#     name="wsr",
#     age=18
# )

# print(user.model_dump())
class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str = "deepseek-chat"
    temperature: float = Field(default=0.7, ge=0, le=2)
    stream: bool = True
 