from fastapi import Query, APIRouter

router = APIRouter()

@router.get("/chat/simple")
async def simple_chat(
    message: str = Query(..., min_length=1, max_length=200)
):
    return {
        "answer": f"你问的是：{message}"
    }

