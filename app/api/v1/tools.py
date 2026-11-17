from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.exceptions import AppException, ErrorCode
from app.schemas.response import ApiResponse

router = APIRouter()

class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="工具名称")

@router.post("/tools/mock-call", response_model=ApiResponse[dict])
async def mock_call_tool(request: ToolCallRequest) -> ApiResponse[dict]:
    """
    模拟调用工具
    """
    if request.tool_name == "error_tool":
        raise AppException(
            message="工具调用失败",
            code=ErrorCode.TOOL_CALL_FAILED,
            status_code=500,
            data={
                "tool_name": request.tool_name
            }
        )

    return ApiResponse[dict](
        data={
            "tool_name": request.tool_name,
            "result": "ok"
        }
    )