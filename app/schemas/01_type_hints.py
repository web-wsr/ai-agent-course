# def add(a:int, b:int) -> int:
#     return a + b

# result = add(1,2)
# print(result)

from typing import Any

name: str = "wsr"
app: int = 30 
score: float = 99.9
is_active: bool = True
extra: Any = {"level": "senior"}
tgs: list[str] = ["tg1", "tg2"]

user: dict[str, Any] = {
    "name": "wsr",
    "age": 29,
    "city": "guangzhou"
}

print (name)
print (app)
print (score)
print (is_active)
print (extra)
print (tgs)
print (user)
