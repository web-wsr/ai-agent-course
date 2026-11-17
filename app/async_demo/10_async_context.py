import asyncio
import httpx
# class AsyncDatabase:
#     async def __aenter__(self):
#         print("打开数据库连接")
#         return self

#     async def __aexit__(self, exc_type, exc_value, traceback):
#         print("关闭数据库连接")

#     async def query(self, sql: str) -> str:
#         await asyncio.sleep(1)
#         return f"查询结果：{sql}"

# async def main():
#     async with AsyncDatabase() as db:
#         result = await db.query("SELECT * FROM users")
#         print(result)

# asyncio.run(main())

async def fetch_url(url: str) -> int:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response

async def main():
    response = await fetch_url("https://example.com")
    print(response)

asyncio.run(main())
