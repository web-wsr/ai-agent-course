import asyncio
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    model: str = "deepseek-chat"
    temperature: float = 0.5

class ChatResponse(BaseModel):
    answer: str
    model: str

async def call_llm(message: str, model: str , temperature: float) -> str:
    print("调用 LLM 模型...")
    print(f"模型：{model}")
    print(f"温度：{temperature}")
    print(f"用户问题：{message}")

    await asyncio.sleep(2)

    return f"AI 回答：你刚才问的是：{message}"
async def chat(request: ChatRequest) -> ChatResponse:
    answer = await call_llm(
        message=request.message,
        model=request.model,
        temperature=request.temperature,
    )
    return ChatResponse(answer=answer, model=request.model)

async def main():
    request = ChatRequest(
        message= "你好",
        model="deepseek-chat",
        temperature=0.5,
    )
    response = await chat(request)
    print(response.model_dump())


asyncio.run(main())