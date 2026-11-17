from pydantic import BaseModel, Field

class ModelInfo(BaseModel):
    name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="模型供应商")
    support_stream: bool = Field(default=True, description="是否支持流式输出")


class ModelListResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list, description="模型列表")