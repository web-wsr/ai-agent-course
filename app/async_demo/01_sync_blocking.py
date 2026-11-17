import time

def query_user():
    print("开始查询用户信息...")
    time.sleep(1)  # 模拟耗时操作
    print("用户信息查询完成！")
    return "查询到的用户信息"

def query_order():
    print("开始查询订单信息...")
    time.sleep(1)  # 模拟耗时操作
    print("订单信息查询完成！")
    return "查询到的订单信息"

def query_llm():
    print("开始查询 AI 回答...")
    time.sleep(1)  # 模拟耗时操作
    print("AI 回答查询完成！")
    return "AI 回答"

def main():
    start = time.perf_counter()

    user = query_user()
    order = query_order()
    llm_answer = query_llm()


    end = time.perf_counter()
    print(user)
    print(order)
    print(llm_answer)
    print(f"总耗时: {end - start:.2f} 秒")


main()