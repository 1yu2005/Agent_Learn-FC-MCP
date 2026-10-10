"""Host 层：Agent 编排核心（Function Calling 主循环）。

完整链路：模型派单 → MCP tools/call 执行 → 结果回填 → 模型作答。
mcp_client 只需提供 list_all_tools / call_tool 两个接口，协议细节被隔离。
"""
import json
import logging

from .llm import chat

logger = logging.getLogger("agent")

SYSTEM_PROMPT = (
    "你是智能助手。当用户需要实时数据时，必须先调用可用工具获取结果，"
    "再基于工具结果组织回答；工具不可用或报错时如实告知，严禁编造。"
)


class Agent:
    """对话编排器：串联 MCP 工具发现、LLM 派单与工具执行"""

    def __init__(self, mcp_client, max_iterations: int = 5):
        self._mcp = mcp_client
        self._max_iterations = max_iterations

    async def run(self, question: str) -> str:
        """执行一次完整对话，返回最终回答"""
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        # 1. 发现工具：MCP tools/list → 转 FC Schema
        tools = await self._mcp.list_all_tools()
        logger.info("MCP 工具发现完成：%s", [t["function"]["name"] for t in tools])

        # 2. FC 主循环
        for _ in range(self._max_iterations):
            result = chat(messages, tools=tools)         # 2.1 模型派单
            messages.append({                            # 2.2 模型回复入历史
                "role": "assistant",
                "content": result["content"],
                "tool_calls": result["tool_calls"] or None,
            })
            if not result["tool_calls"]:                 # 2.3 无派单 → 直接作答
                return result["content"]
            for tc in result["tool_calls"]:              # 2.4 执行派单
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"] or "{}")
                logger.info("执行工具：%s(%s)", name, args)
                output = await self._mcp.call_tool(name, args)
                logger.info("工具返回：%s", output)
                messages.append({                        # 2.5 结果回填
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": output,
                })
        return "已达最大迭代次数，任务终止。"
