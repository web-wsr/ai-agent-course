import asyncio
import time


async def query_user():
    print("开始查询用户信息")
    await asyncio.sleep(1)
    print("用户信息查询完成")
    return "用户信息"


async def query_order():
    print("开始查询订单信息")
    await asyncio.sleep(1)
    print("订单信息查询完成")
    return "订单信息"


async def query_llm():
    print("开始调用大模型")
    await asyncio.sleep(2)
    print("大模型返回结果")
    return "AI 回答"

async def main():
    start = time.perf_counter()

    user, order, llm_answer = await asyncio.gather(
        query_user(),
        query_order(),
        query_llm(),
    )

    end = time.perf_counter()
    print(user)
    print(order)
    print(llm_answer)
    print(f"总耗时: {end - start:.2f} 秒")

asyncio.run(main())