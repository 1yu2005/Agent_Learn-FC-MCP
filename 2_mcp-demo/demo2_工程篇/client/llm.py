"""LLM 调用层：封装 OpenAI 兼容接口，返回统一结构供 Agent 编排"""
from openai import OpenAI

from .config import get_config

_cfg = get_config()
_client = OpenAI(            # 初始化 OpenAI 客户端
    base_url=_cfg["base_url"],
    api_key=_cfg["api_key"],
    timeout=_cfg["timeout"],
)


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """向模型发起一次对话请求。

    Returns:
        {"content": 模型回复文本,
         "tool_calls": [{"id", "type", "function": {"name", "arguments"}}, ...]}
    """
    kwargs: dict = {"model": _cfg["model"], "messages": messages}
    if tools:
        kwargs["tools"] = tools

    resp = _client.chat.completions.create(**kwargs)   # 发起对话请求
    choice = resp.choices[0]                           # 提取第一个回复

    return {
        "content": choice.message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {"name": tc.function.name,
                             "arguments": tc.function.arguments},
            }
            for tc in (choice.message.tool_calls or [])
        ],
    }
    # ps:模型返回内容的格式见D:\Agent\AI Agent 面试全攻略\code\04_工具调用\2_mcp-demo\demo1.md
