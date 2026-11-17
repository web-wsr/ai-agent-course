from app.schemas.model import ModelInfo, ModelListResponse

async def get_models() -> ModelListResponse:
    return ModelListResponse(
        models=[
            ModelInfo(name="deepseek-chat", provider="deepseek", support_stream=False),
            ModelInfo(name="qwen-plus", provider="alibaba"),
            ModelInfo(name="gpt-4o-mini", provider="openai"),
            ModelInfo(name="gpt-3.5-turbo", provider="openai"),
        ]
    )