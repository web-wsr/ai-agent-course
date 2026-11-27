import asyncio

from app.llm.factory import LLMProviderFactory
from app.services.structured_output_service import structured_output_service


async def main():
    provider = LLMProviderFactory.create("glm")

    questions = [
        "我的订单怎么还没发货？",
        "我想退款，怎么操作？",
        "这款衣服有黑色吗？",
        "我要找人工客服。",
    ]

    for question in questions:
        result = await structured_output_service.classify_intent(
            user_question=question,
            model="glm-5.3-flash",
            llm_provider=provider,
        )

        print("question:", question)
        print(result.model_dump())
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
