import asyncio
import json

import httpx
from app.core.config import settings


async def main():
    if not settings.glm_api_key:
        raise RuntimeError("请在 .env 中设置 GLM_API_KEY")

    url = f"{settings.glm_base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.glm_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "GLM-5.3-Flash",
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的 AI Agent 课程助教",
            },
            {
                "role": "user",
                "content": "请用一句话解释什么是 AI Agent",
            },
        ],
        "temperature": 0.7,
        "stream": True,
    }

    full_answer = ""

    async with (
        httpx.AsyncClient(timeout=30) as client,
        client.stream("POST", url, json=payload, headers=headers) as response,
    ):
        response.raise_for_status()
        print("流式输出：")

        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue

            data = line[5:].strip()
            if data == "[DONE]":
                break

            chunk = json.loads(data)
            choices = chunk.get("choices", [])
            if not choices:
                continue

            content = choices[0].get("delta", {}).get("content")
            if content:
                print(content, end="", flush=True)
                full_answer += content

    print("\n\nfull_answer:", full_answer)


if __name__ == "__main__":
    asyncio.run(main())
