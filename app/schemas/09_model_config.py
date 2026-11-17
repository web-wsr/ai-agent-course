from pydantic import BaseModel, Field, ConfigDict

class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId", description="会话ID")
    message: str

request1 = ChatRequest(
    sessionId="s_1000",
    message="你好"
)

request2 = ChatRequest(
    session_id="s_1001",
    message="你好"
)

# print(request.model_dump())
# print(request.model_dump(by_alias=True))
# print(request.session_id)
print(request1.model_dump())
print(request2.model_dump())