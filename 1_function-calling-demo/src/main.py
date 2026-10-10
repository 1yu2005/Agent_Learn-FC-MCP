"""入口：命令行问答。"""
import logging

from .agent import run_agent   # 导入主循环函数 run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    print("本地 Qwen Function Calling 演示（输入 exit 退出）")
    while True:
        question = input("你: ").strip()      # 读取用户输入，去掉首尾空格
        if question.lower() in {"exit", "quit"}:
            break
        answer = run_agent(question)  # 调用主循环函数 run_agent，传入用户输入
        print(f"助手: {answer}\n")

# (venv) D:\Agent\AI Agent 面试全攻略\code\04_工具调用\1_function-calling-demo>python -m src.main  ⭐⭐⭐⭐⭐