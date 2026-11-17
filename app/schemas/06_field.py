from pydantic import BaseModel, Field, ValidationError

class ChatRequest(BaseModel):
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=1024,
        description="用户输入的消息"
    )
    model: str = Field("deepseek-chat", description="使用的模型名称")
    temperature: float = Field(
        default=0.5, 
        ge=0, 
        le=1,
        description="生成文本的随机性参数"
    )
    stream: bool = Field(default=True, description="是否启用流式输出")


# request = ChatRequest(message="什么是 LangGraph?")

# print(request.model_dump())

try:
    request = ChatRequest(message="你好", temperature=3)
except ValidationError as e:
    print(e)