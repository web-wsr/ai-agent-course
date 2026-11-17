import asyncio

async def query_order():
    await asyncio.sleep(1)
    raise ValueError("查询订单信息出错")

# async def main():
#     try:
#         result = await query_order()
#         print(result)
#     except ValueError as e:
#         print(f"捕获到异常: {e}")

# asyncio.run(main())
async def query_user():
    await asyncio.sleep(1)
    return "用户信息"

async def main():
    results = await asyncio.gather(
        query_order(),
        query_user(),
        return_exceptions=True
    )
    # print(results)
    for result in results:
        if isinstance(result, Exception):
            print(f"任务失败: {result}")
        else:
            print(f"任务成功: {result}")


asyncio.run(main())