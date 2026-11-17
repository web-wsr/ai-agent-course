from pydantic import BaseModel, Field, ValidationError

class Message(BaseModel):
    role: str = Field(..., description="消息的角色，例如 'user' 或 'assistant'")
    content: str = Field(..., min_length=1,description="消息的内容")

class ChatRequest(BaseModel):
    message: list[Message] = Field(..., description="对话消息列表")
    model: str = Field(default="deepseek-chat", description="模型名称")

# request = ChatRequest(
#     message=[
#         Message(role="system", content="你是一个AI助手"),
#         Message(role="user", content="你好"),
#     ],
# )

# print(request.model_dump())

try:
    request = ChatRequest(
        message=[
            {"role": "system", "content": ""}
        ]
    )

except ValidationError as e:
    print(e)