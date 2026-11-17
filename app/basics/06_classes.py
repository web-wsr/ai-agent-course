class User: 
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def greet(self):
        return f"Hello, my name is {self.name} and I am {self.age} years old."

user = User("Alice", 30)

print(user.greet())  # 输出: Hello, my name is Alice and I am 30 years old.