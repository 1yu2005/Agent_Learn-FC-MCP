"""程序入口：交互式问答。

启动命令（必须在项目根目录）：
    python -m client.main
"""
import asyncio
import logging

from .agent import Agent
from .config import get_config
from .logging_config import setup_logging
from .mcp_client import MCPClientManager


async def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")
    cfg = get_config()

    # 聚合两个 Server：weather（本地工具） + xxapi（外部 API 工具）
    mcp_client = MCPClientManager(
        [
            {"name": "weather",
             "command": cfg["server_command"], "args": ["-m", "server.weather_server"]},
            {"name": "xxapi",
             "command": cfg["server_command"], "args": ["-m", "server.xxapi_server"]},
        ]
    )
    agent = Agent(mcp_client=mcp_client, max_iterations=cfg["max_iterations"])

    print("MCP + Function Calling Demo（输入 exit 退出）")
    while True:
        question = input("\n问题：").strip()
        if question.lower() in ("exit", "quit"):
            break
        try:
            answer = await agent.run(question)
            print(f"\nAgent: {answer}")
        except Exception as exc:
            logger.exception("对话执行异常")
            print(f"\nAgent: 抱歉，本次对话异常：{exc}")


if __name__ == "__main__":
    asyncio.run(main())
