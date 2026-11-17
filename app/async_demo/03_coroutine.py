import asyncio

async def query_user():
    return "查询到的用户信息"

async def main():
    result = await query_user()
    print(result)

asyncio.run(main())