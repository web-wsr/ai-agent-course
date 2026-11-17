import asyncio

async def call_llm():
    print("调用 LLM 模型...")
    await asyncio.sleep(5)
    return "AI 回答"

async def main():
    try:
        result = await asyncio.wait_for(
            call_llm(),
            timeout=3
        )
        print(result)
    except asyncio.TimeoutError:
        print("超时")

asyncio.run(main())