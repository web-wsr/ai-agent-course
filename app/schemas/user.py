from enum import Enum

from pydantic import BaseModel, Field

class UserRole(str, Enum):
    """
    用户角色
    """
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class CurrentUser(BaseModel):
    """
    当前用户信息
    """
    user_id: str = Field(...,description="用户 ID")
    username: str = Field(...,description="用户名")
    role: UserRole = Field(default=UserRole.USER,description="用户角色")
    is_active: bool = Field(default=True,description="是否激活")