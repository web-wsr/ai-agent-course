from app.core.config import settings
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.schemas import LLMProviderName


class DeepSeekProvider(OpenAICompatibleProvider):
    provider_name: LLMProviderName = LLMProviderName.DEEPSEEK

    def __init__(
        self,
    ):
        super().__init__(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            defalt_model="deepseek-chat",
            timeout_seconds=settings.llm_timeout_seconds,
        )
