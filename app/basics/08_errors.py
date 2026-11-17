def divide(a:int, b:int) ->float:
    return a / b

try:
    result = divide(10, 0)
    print(result)
except ZeroDivisionError as e:
    print(f"除数不能为0: {e}")
except Exception as e:
    print(f"发生错误: {e}")
finally:
    print("不管错误与否，都会执行")

# 自定义异常 class类
class ModelNotFoundError(Exception):
    pass
#定义函数
def get_model(model_name:str) -> str:
    supported_models = ["deepseek-chat", "gpt-3.5-turbo","gpt-4"]
    if model_name not in supported_models:
        raise ModelNotFoundError(f"模型{model_name}不存在")
    return model_name

try:
    model = get_model("glm-5.2")
    print(model)
except ModelNotFoundError as e:
    print(f"模型错误: {e}")
