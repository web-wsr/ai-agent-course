from fastapi import APIRouter, HTTPException, status

from app.schemas.response import ApiResponse
from app.services.prompt_service import prompt_service

router = APIRouter()


@router.get("/prompts", response_model=ApiResponse[list[dict]])
async def list_prompts() -> ApiResponse[list[dict]]:
    prompts = prompt_service.list_prompts()

    return ApiResponse[list[dict]](
        data=[
            {
                "prompt_id": prompt.prompt_id,
                "name": prompt.name,
                "scenario": prompt.scenario.value,
                "version": prompt.version,
                "description": prompt.description,
                "required_variables": prompt.required_variables,
            }
            for prompt in prompts
        ]
    )


@router.get("/prompts/{prompt_id}", response_model=ApiResponse[dict])
async def get_prompt_detail(
    prompt_id: str,
    version: str = "v1",
):
    try:
        prompt = prompt_service.get_prompt(prompt_id, version)
    except KeyError as exc:
        available_versions = sorted(
            item.version
            for item in prompt_service.list_prompts()
            if item.prompt_id == prompt_id
        )

        if available_versions:
            detail = (
                f"Prompt 版本不存在：{prompt_id}@{version}，"
                f"可用版本：{', '.join(available_versions)}"
            )
        else:
            detail = f"Prompt 不存在：{prompt_id}"

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc

    return ApiResponse[dict](data=prompt.model_dump())
