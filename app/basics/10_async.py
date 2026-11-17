import asyncio

# async def fetch_data():
#     print("开始获取数据...")
#     await asyncio.sleep(2)  # 模拟异步操作
#     print("数据获取完成！")
#     return "获取到的数据"

# result = asyncio.run(fetch_data())
# print(result)  # 输出: 获取到的数据

# async def query_user():
#     await asyncio.sleep(1)
#     return "查询到的用户信息"

# async def query_order():
#     await asyncio.sleep(1)
#     return "查询到的订单信息"

# async def query_llm():
#     await asyncio.sleep(1)
#     return "AI 回答"

# async def main():
#     user, order, llm = await asyncio.gather(
#         query_user(),
#         query_order(),
#         query_llm()
#     )
#     print(user)
#     print(order)
#     print(llm)

# asyncio.run(main())

# async def generate_tokens():
#     tokens = ["你", "好", ", ", "世", "界", "杯","!"]

#     for token in tokens:
#         await asyncio.sleep(1)
#         yield token

# async def main():
#     async for token in generate_tokens():
#         print(token, end="", flush=True)

#     print()  # 换行

# asyncio.run(main())

class AsyncDatabase:
    async def __aenter__(self):
        print("连接数据库...")
        await asyncio.sleep(1)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("关闭数据库连接...")

    async def query(self, sql: str) -> str:
        print(f"执行查询: {sql}")
        await asyncio.sleep(1)
        return "查询结果"
async def main():
    async with AsyncDatabase() as db:
        result = await db.query("SELECT * FROM users")
        print(result)

asyncio.run(main())