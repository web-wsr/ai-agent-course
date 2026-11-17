from typing import Literal

ModelName = Literal["glm-5.2", "deepseek-chat", "gpt-3.5-turbo"]

def chat(message: str, model: ModelName) -> str:
    return f"使用 {model} 模型回答：{message}"

print(chat("你好", "glm-5.2"))

from enum import Enum

class MessageRole(str, Enum):
    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL = 'tool'

def create_message(role: MessageRole, content: str) -> dict[str,str]:
    return {
        'role': role.value,
        'content': content,
    }
print(create_message(MessageRole.USER, "你好"))