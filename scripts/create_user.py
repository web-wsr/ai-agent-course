import asyncio

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.repositories.user_repository import UserRespository
from app.schemas.user import CurrentUser, UserRole


async def main():
    repository = UserRespository()
    request = CurrentUser(
        user_id="",  # 仓库自动生成 ID，不使用请求中的 user_id。
        username="dawei",
        role=UserRole.USER,
    )

    async with AsyncSessionLocal() as db:
        user = await repository.create_user(db=db, request=request)
        saved_user = await repository.get_user_by_id(db=db, user_id=user.id)
        verify_user(saved_user, request)

        print("用户创建成功，按 ID 查询验证通过")
        print(f"user_id: {user.id}")
        print(f"username: {user.username}")
        print(f"role: {user.role}")
        print(f"is_active: {user.is_active}")


def verify_user(user: User | None, request: CurrentUser):
    assert user is not None, "按 ID 查询未找到刚创建的用户"
    assert user.username == request.username, "用户名不一致"
    assert user.role == request.role.value, "角色不一致"
    assert user.is_active == request.is_active, "激活状态不一致"


if __name__ == "__main__":
    asyncio.run(main())
