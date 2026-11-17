import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import CurrentUser

class UserRespository:
    async def create_user(
            self,
            db: AsyncSession,
            request: CurrentUser,
    ) -> User:
        user = User(
            id=f"u_{uuid.uuid4().hex[:8]}",
            role=request.role,
            username=request.username,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_user_by_id(
            self,
            db: AsyncSession,
            user_id: str,
    ) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

user_repository = UserRespository()
    
