from pydantic import BaseModel, ValidationError

class ChatRequest(BaseModel):
    message: str
    model: str = "deepseek-chat"
    temperature: float = 0.7
    stream: bool = True

# try:
#     request = ChatRequest(
#         message=123,
#         temperature="0.5",
#         stream=True,
#     )
# except ValidationError as e:
#     print(e)

request = ChatRequest(
    message="什么是 LangGraph?"
)

json_str = request.model_dump_json()
print(json_str)
print(type(json_str))


