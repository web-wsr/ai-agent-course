from app.llm.schemas import LLMResponse, LLMUsage


def parse_chat_completion_response(data: dict) -> LLMResponse:
    choices = data["choices"][0]
    message = choices["message"]
    usage_data = data.get("usage", {})

    usage = LLMUsage(
        prompt_tokens=usage_data.get("prompt_tokens", 0),
        completion_tokens=usage_data.get("completion_tokens", 0),
        total_tokens=usage_data.get("total_tokens", 0),
    )

    return LLMResponse(
        model=data.get("model", ""),
        content=message.get("content", ""),
        raw_response=data,
        usage=usage,
    )
