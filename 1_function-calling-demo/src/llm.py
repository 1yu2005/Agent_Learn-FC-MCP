"""LLM 客户端：OpenAI SDK 对接本地 Ollama（OpenAI 兼容协议）。

切换云端模型（GPT/DeepSeek）只需改 .env 的 OLLAMA_BASE_URL，业务代码零改动。

=====================================================================
在该文件夹中：定义了对话时调用的函数，在函数中明确定义了使用哪一个LLM模型，函数返回的是标准化的助手回复字典。
标准化的助手回复字典格式：
    {
        "role": "assistant",
        "content": 模型回复文本（无工具调用时为最终回答）,
        "tool_calls": [
            {"id": "...", "type": "function",
             "function": {"name": "get_weather", "arguments": '{"city": "北京"}'}}
        ]  # 无工具调用时为 []
    }
_client.chat.completions.create(**kwargs)  在这关键字参数中，包含：
    model：模型名称
    messages：对话历史消息列表
    tools：工具调用列表（JSON Schema）
"""
from openai import OpenAI

from .config import OLLAMA_BASE_URL,OLLAMA_MODEL  # 从config模块导入Ollama配置

_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")  # 本地不校验，任意非空  ⭐⭐⭐⭐⭐

def chat(messages:list[dict],tools:list[dict] | None = None) -> dict: # | 表示可选参数
    """发起一次对话请求，返回标准化 message
    
    :param messages: 对话历史消息列表，包含用户和助手的消息。  OpenAI 格式：{"role": "user", "content": "你好"} 或 {"role": "assistant", "content": "你好，我是一个助手"}
    :param tools: 工具声明列表（JSON Schema）
    :return: 包含助手回复的字典，格式为 统一格式的 dict:
        {
            "role": "assistant",
            "content": 模型回复文本（无工具调用时为最终回答）,
            "tool_calls": [
                {"id": "...", "type": "function",
                 "function": {"name": "get_weather", "arguments": '{"city": "北京"}'}}
            ]  # 无工具调用时为 []
        }"""

    kwargs:dict ={"model":OLLAMA_MODEL,"messages":messages}  # 初始化请求参数  ⭐⭐⭐⭐⭐

    if tools :    # 如果提供了工具调用列表
        kwargs["tools"] = tools

    resp = _client.chat.completions.create(**kwargs)  # 调用模型，发起对话请求  ⭐⭐⭐⭐⭐
    msg = resp.choices[0].message    # # 取出首个 choice（对话场景通常只看第一个）
    return {
        "content":msg.content or "",
        "tool_calls":[
            {
                "id":tc.id,
                "type":"function",
                "function":{"name":tc.function.name,"arguments":tc.function.arguments},
            }
            for tc in (msg.tool_calls or [])
        ],
    }    

