from pydantic import BaseModel, ValidationError

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

request = ChatRequest(message="Hi")
print(request.message)
print(request.session_id)
print(request.model_dump())  # 输出: {'message': 'Hi', 'session_id': None}

try:
    request = ChatRequest(message=123)  # 错误的类型
except ValidationError as e:
    print(e)  # 输出: 1 validation error for ChatRequest
              # message
              #   str type expected (type=type_error.str) 
# 嵌套模型
class Message(BaseModel):
    content: str
    role: str

class ChatRequest(BaseModel):
    message: list[Message]
    model: str = "deepseek-chat"

request = ChatRequest(
    message=[
        Message(role="system", content="你是一个AI助手"),
        Message(role="user", content="你好"),
    ],
)
print(request.model_dump())