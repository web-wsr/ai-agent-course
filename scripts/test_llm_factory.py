from app.llm.factory import LLMProviderFactory, infer_provider_from_model

models = ["deepseek-chat", "qwen-plus", "gpt-4o-mini", "glm-5.3-flash"]

for model in models:
    provider = infer_provider_from_model(model)
    print(f"{model} -> {provider}")
