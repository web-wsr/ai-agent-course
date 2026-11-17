from fastapi import Header, HTTPException, status, Depends

from app.schemas.user import CurrentUser, UserRole
from app.core.config import settings
from app.core.request_context import set_user_id


async def verify_api_key(
        x_api_key: str | None = Header(default=None),
) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少请求头 x-api-key",
        )

    if x_api_key != settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key 不正确",
        )

    return x_api_key

async def get_current_user(
        ## 获取用户之前，必须先校验API KEY
        api_key: str = Depends(verify_api_key),
        x_user_id: str | None = Header(default=None),
        x_username: str | None = Header(default=None),
        x_user_role: str | None = Header(default="user"),
) -> CurrentUser:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少请求头 x-user-id",
        )

    if not x_username: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少请求头 x-username",
        )

    role = UserRole.ADMIN if x_user_role == "admin" else UserRole.USER

    ## 写入user_id 上下文
    set_user_id(x_user_id)

    return CurrentUser(
        user_id=x_user_id,
        username=x_username,
        role=role,
        is_active=True
    )

## 权限依赖：只允许管理员访问
async def require_admin(
        current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，管理员才能访问",
        )
    return current_user


## 权限依赖： 禁用用户不能访问

async def require_active_user(
        current_user: CurrentUser=Depends(get_current_user)
) -> CurrentUser:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用，无法访问",
        )
    return current_user