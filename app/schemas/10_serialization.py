from pydantic import BaseModel

class ChatResponse(BaseModel):
    answer: str
    session_id: str | None = None
    trace_id: str | None = None

response = ChatResponse(answer="你好，我是 AI")

print(response.model_dump())
print(response.model_dump(exclude_none=True))