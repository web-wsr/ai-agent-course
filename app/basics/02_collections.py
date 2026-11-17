fruits = ["apple", "banana", "cherry", "date", "elderberry"]
fruits.append("fig")

for fruit in fruits:
    print(fruit)

numbers = [1, 2, 3, 4, 5]
#列表推导式
doubled = [num *2 for num in numbers]
print(doubled)

# 带条件的列表推导式

big_numbers = [num for num in numbers if num > 2]
print(big_numbers)

user = {
    "name": "Alice",
    "age": 30,
}
print(user.get("name"))
print(user.get("age"))
print(user.get("email")) 
print(user.get("city", "未填写")) # 类似于js user.email ?? "未填写"

for key, value in user.items():
    print(f"{key}: {value}")
