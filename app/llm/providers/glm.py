from app.core.config import settings
from app.llm.providers.openai_compatible import OpenAICompatibleProvider
from app.llm.schemas import LLMProviderName


class GLMProvider(OpenAICompatibleProvider):
    provider_name: LLMProviderName = LLMProviderName.GLM

    def __init__(self):
        super().__init__(
            api_key=settings.glm_api_key,
            base_url=settings.glm_base_url,
            defalt_model="glm-5.3-flash",
            timeout_seconds=60,
        )
