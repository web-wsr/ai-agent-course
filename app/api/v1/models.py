from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.model import ModelListResponse
from app.schemas.response import ApiResponse
from app.schemas.user import CurrentUser
from app.services.model_service import get_models

router = APIRouter()


@router.get("/models", response_model=ApiResponse[ModelListResponse])
async def list_models(
    admin_user: Annotated[CurrentUser, Depends(require_admin)],
):
    result = await get_models()
    return ApiResponse[ModelListResponse](data=result)
