from app.core.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.providers import (
    DeepSeekProvider,
    GLMProvider,
    OpenAIProvider,
    QwenProvider,
)
from app.llm.schemas import LLMProviderName


class LLMProviderFactory:
    @staticmethod
    def create(provider: LLMProviderName | str | None = None) -> BaseLLMProvider:
        provider_name = provider or infer_provider_from_model(settings.default_model)

        if isinstance(provider_name, str):
            provider_name = LLMProviderName(provider_name)

        if provider_name == LLMProviderName.DEEPSEEK:
            return DeepSeekProvider()

        if provider_name == LLMProviderName.OPENAI:
            return OpenAIProvider()

        if provider_name == LLMProviderName.QWEN:
            return QwenProvider()

        if provider_name == LLMProviderName.GLM:
            return GLMProvider()

        raise ValueError(f"不支持的 LLM Provider: {provider_name}")


def infer_provider_from_model(model: str) -> LLMProviderName:
    if model.startswith("deepseek"):
        return LLMProviderName.DEEPSEEK

    if model.startswith("qwen"):
        return LLMProviderName.QWEN

    if model.lower().startswith("glm"):
        return LLMProviderName.GLM

    if model.startswith(("gpt", "openai")):
        return LLMProviderName.OPENAI

    return LLMProviderName.DEEPSEEK
