def get_user_name(user_id: int) -> str | None:
    if user_id == 1:
        return "wsr"

print(get_user_name(1))
print(get_user_name(2))


from pydantic import BaseModel

class UserA(BaseModel):
    name: str
    email: str | None

class UserB(BaseModel):
    name: str
    email: str | None = None

print(UserA(name="wsr", email=None))

