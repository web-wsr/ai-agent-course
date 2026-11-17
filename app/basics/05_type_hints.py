def add(a: int, b: int) -> int:
    return a + b

# python 的类型注解默认只是类型提示，不是强制校验

print(add("1", "2")) # 输出: 12

from typing import Any

name: str = "wsr"
age: int = 29
scorce: float = 99.9
tgs: list[str] = ["tg1", "tg2"]
user: dict[str, Any] = {
    "name": "wsr",
    "age": 29,
}

def get_user_name(user_id: int) -> str | None:
    if user_id == 1:
        return "wsr"
    else:
        return None

print(get_user_name(1))
print(get_user_name(2))