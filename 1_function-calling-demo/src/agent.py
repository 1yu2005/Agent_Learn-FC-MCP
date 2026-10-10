"""Agent 主循环：模型决策 -> 平台执行 -> 结果回填，直到模型给出最终回答。

对应文档"四角色五步"：
① 用户 -> 平台：问题
② 平台 -> 模型：问题 + 工具 JSON Schema
③ 模型 -> 平台：tool_calls 指令（未真正执行）
④ 平台 -> 工具：真正调用并拿到结果
⑤ 平台 -> 模型 -> 用户：结果回填（role=tool），模型组织最终回答

感觉此处的run_agent函数就是所谓的平台：在这个函数中能够接触用户的问题、知道工具说明列表、能够调用llm模型进行对话、能够调用工具执行器、管理着所有历史对话消息。
===============================================================
在这个文件中：
1.定义了主循环函数 run_agent，用于处理用户问题、与模型交互、调用工具并组织最终回答。
2.在这个主函数中包含历史对话消息、同时调用LLM模型进行对话（chat函数，传入历史对话记录和工具说明书列表）、根据模型回复的结果中的 tool_calls 判断是否需要调用工具以及调用哪个工具。
  如果要调用工具，就会调用execute_tool函数，传入工具名和参数字符串。然后将工具执行结果回填到模型回复中。
  如果不需要调用工具，就会直接返回模型回复。
"""
import logging   # 导入logging模块，用于日志记录

from .config import MAX_ITERATIONS
from .llm import chat              # 从llm模块导入chat函数，用于与模型交互
from .tools.registry import TOOL_SCHEMAS, execute_tool  # 从tools模块导入TOOL_SCHEMAS（工具说明书列表）和execute_tool函数(执行工具)

logger = logging.getLogger(__name__)


def run_agent(user_question: str) -> str:
    """以用户问题启动一轮工具调用循环，返回模型最终回答。"""
    messages: list[dict] = [
        {"role": "system", "content": "你是一个贴心的助手，需要天气信息时请调用 get_weather。"},
        {"role": "user", "content": user_question},
    ]

    for _ in range(MAX_ITERATIONS):  # 防死循环烧钱
        '''
        如果要调用工具，则至少会有两次循环：
        执行工具；
        把工具结果以 role="tool" 回填到 messages；
        当前循环结束；
        进入下一次 for 循环；
        第二次调用 chat，让模型根据工具结果组织最终回答。
        '''
        msg = chat(messages, tools=TOOL_SCHEMAS)   # ⭐⭐⭐⭐⭐ 调用LLM模型，进行对话。参数包括历史消息和工具说明书列表。函数返回的是标准化的助手回复字典

        # 回填 assistant 消息（含 tool_calls，供下一轮对号入座）
        messages.append(
            {
                "role": "assistant",
                "content": msg["content"] or None,
                "tool_calls": msg["tool_calls"] or None,
            }
        )

        if not msg["tool_calls"]:  # 模型不再要工具 -> 出结果 
            return msg["content"]

        for tc in msg["tool_calls"]:  # ⭐⭐⭐⭐⭐ 平台执行所有工具并回填结果   msg["tool_calls"] 是一个列表，每个元素是一个字典，包含工具调用的 id、类型、函数名和参数字符串。 详见llm.py的返回值的格式
            result = execute_tool(tc["function"]["name"], tc["function"]["arguments"])  # 调用工具执行器，传入工具名和参数字符串
            logger.info("执行工具 %s -> %s", tc["function"]["name"], result)             # 记录工具执行日志，实际显示中会打印该行日志，显示工具调用的函数名和参数字符串，以及工具执行器返回的结果
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    raise RuntimeError(f"超过最大迭代次数 {MAX_ITERATIONS}，已中止")
