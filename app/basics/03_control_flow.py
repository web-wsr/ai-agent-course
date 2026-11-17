score = 85
age = 18
is_vip = True

if score >= 90:
    print("A")
elif score >= 80:
    print("B")
elif score >= 70:
    print("C")
elif score >= 60:
    print("D")
else:
    print("F")

# 逻辑运算符
if age>=18 and is_vip:
    print("成年人且是VIP用户")
if age<18 or is_vip:
    print("未成年人或VIP用户")   
if not age<18:
    print("成年人")
else:
    print("成年人") 

for i in range(5):
    print(i)

# enumerate 获取索引
fruits = ["apple", "banana", "cherry"]
for index, fruit in enumerate(fruits):
    print(f"索引: {index}, 水果: {fruit}")
