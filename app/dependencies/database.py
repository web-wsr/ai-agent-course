from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

# class MockDBSession:
#     async def excute(self, sql: str) -> str:
#         return f"执行 SQL: {sql}"

#     async def close(self):
#         print("关闭MockDBSession连接")

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()