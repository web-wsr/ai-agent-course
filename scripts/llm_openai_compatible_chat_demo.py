import asyncio

import httpx
from app.core.config import settings


async def main():
    if not settings.openai_api_key:
        raise RuntimeError("请在 .env 中设置 OPENAI_API_KEY")

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
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
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)

        print("status_code:", response.status_code)
        print("response:")
        print(response.text)

        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            print("answer:", answer)
            print("usage:", usage)


if __name__ == "__main__":
    asyncio.run(main())
