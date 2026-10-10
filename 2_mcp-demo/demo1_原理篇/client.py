"""【原理篇】 手写MCP Client: JSON-RPC 2.0 + stdio

Client 是Host内的连接器，与单个Server建立1:1的会话，转发请求、接收响应、管理连接状态
Client 负责：拉起Server子进程——>通过管道（stdio）发请求——>接收响应    ps:stdio标准输入输出，适用于本地（即Server作为Host的子进程）  还有一种是Streamable HTTP适用远程

本文件把“发送的每条请求”和“接收的每条响应”都打印出来，
跑一次就能直观看到MCP协议是怎么交换消息的

两种运行模式：
    python client.py          # 模式1：手动调工具，看清协议消息
    python client.py --llm    # 模式2：接入大模型看清MCP是怎么给LLM提供工具的
"""

import json            # 用于解析 JSON 字符串
import sys             # 用于获取标准输入输出
import subprocess      # 用于拉起Server子进程
import urllib.request  # 模式2用：调本地Ollama（标准库即可，无需openai包）

# ========================传输层：拉起Server进程======================= ⭐⭐
class ProtocolMCPClient:
    """手写MCP Client:每个方法对应MCP协议的一个方法"""

    def __init__(self,server_cmd:list[str]):  #  ⭐
        # 启动Server子进程，接好 stdin/stdout 两条管道
        # 这一步就是 Transport（stdio传输）两个进程通过管道说话
        self._proc = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,    # 我们往这里写，Server从它的stdin读取 ⭐⭐⭐⭐⭐
            stdout=subprocess.PIPE,   # Server往它的stdout写，我们从这里读取 ⭐⭐⭐⭐⭐
            text=True,                 # 以文本模式读写，避免编码问题
            encoding="utf-8",
        )
        self._next_id = 1             # JSON-RPC用自增id对应请求和响应

    def _request(self,method:str,params:dict | None = None) -> dict:  #  ⭐  # params 这个参数可以不传；不传时是 None；如果传，期望传一个字典。即 params是可选参数
        """发送一条JSON-RPC请求，并等Server的响应"""
        req = {"jsonrpc":"2.0","id":self._next_id,"method":method}  # ⭐⭐⭐⭐⭐
        if params is not None:
            req["params"]=params
        self._next_id += 1  # 每次请求id自增

        # ---打印：让初学者看清“发送的每条请求”---
        print(f"\n【Client发送】{json.dumps(req,ensure_ascii=False)}")

        # 写方向：把请求写成一行JSON,写入Server的stdin  ⭐
        self._proc.stdin.write(json.dumps(req,ensure_ascii=False)+"\n")
        self._proc.stdin.flush()  # flush() 确保写入立即生效，避免缓存问题

        # 读方向：从Server的stdout读一行JSON（阻塞等待Server回复） ⭐
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("Server 进程无响应，请检查 server.py 是否可正常运行")
        response = json.loads(line)

        #---打印：让初学者看清“Server回了什么”---
        print(f"【Server响应】{line.strip()}")
        return response

    # ===== 下面三个方法就是 MCP 协议的核心方法 =====

    def initialize(self) -> dict: #  ⭐
        """协议方法 initialize：握手，确认协议版本与能力"""
        return self._request("initialize")

    def list_tools(self) -> list: #  ⭐
        """协议方法 list_tools：问Server有哪些工具，获取Server提供的工具列表（Schema）"""
        resp = self._request("tools/list")
        return resp.get("result",{}).get("tools",[])

    def call_tool(self, name: str, arguments: dict) -> str: #  ⭐
        """协议方法 tools/call：请 Server 执行某个工具，返回结果文本"""
        resp = self._request("tools/call", {"name": name, "arguments": arguments})
        content = resp.get("result", {}).get("content", [])
        # MCP 结果结构：content 是文本块列表，逐个取 text 拼起来
        return "\n".join(item.get("text", "") for item in content)

    def close(self) -> None:
        """收尾：关掉 Server 子进程"""
        self._proc.terminate()

# ===================== 模式1：手动调工具（先跑这个！） =====================
def demo_manual(client: ProtocolMCPClient) -> None:  # 参数：client 是一个 ProtocolMCPClient 实例
    """手动依次调用协议方法，完整走一遍 MCP 流程"""
    print("=" * 60)
    print("模式1：手动调用 MCP 协议方法，观察消息流动")
    print("=" * 60)

    client.initialize()                    # 第1步：握手
    tools = client.list_tools()            # 第2步：发现工具
    print(f"\n>>> Server 共提供 {len(tools)} 个工具："
          f"{[t['function']['name'] for t in tools]}")

    # 第3步：直接调用工具（注意：此时还没有大模型参与，就是两个进程在通信）
    result = client.call_tool("get_weather", {"city": "北京"})
    print(f">>> 工具执行结果：{result}")

    result = client.call_tool("get_current_time", {})
    print(f">>> 工具执行结果：{result}")

    print("\n到这里你应该已经看明白了：")
    print("  MCP 就是两个进程按约定好的格式（JSON-RPC 一行一行）互相说话，")
    print("  Server 把工具包装起来，Client 通过协议调用。")

# ===================== 模式2：接入大模型（理解 MCP 的作用） =====================
# 模式2 才回答"MCP 有什么用"：把 Server 的工具交给大模型，
# 让模型根据用户问题自动决定调用哪个工具（这就是和 Function Calling 结合）。

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL = "qwen-8B-finetune-int4:latest"


def call_llm(messages: list[dict], tools: list[dict]) -> dict:
    """用 urllib 调本地 Ollama（OpenAI 兼容接口），返回模型的回复"""
    body = {"model": MODEL, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),          # 请求体    
        headers={"Content-Type": "application/json"},   # 请求头
    )
    with urllib.request.urlopen(req) as resp:  # 发送请求，等待响应
        # 读取响应体，解码为 JSON 字典串
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]  # 取第一个回复，因为是单线程
'''
data["choices"][0]["message"] 是模型回复的 JSON 字典串。
// 情形一：普通文本
{
  "role": "assistant",
  "content": "北京的天气是晴，25°C。",
  "reasoning_content": null     // 模型的推理内容。推理模型才有此字段，普通模型没有
}

// 情形二：要调用工具
{
  "role": "assistant",
  "content": null,     // ⭐
  "tool_calls": [      // ⭐
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_weather",
        "arguments": "{\"city\": \"北京\"}"
      }
    }
  ]
}
'''


def demo_with_llm(client: ProtocolMCPClient) -> None:
    """模式2：MCP + Function Calling 完整链路"""
    print("=" * 60)
    print("模式2：MCP 给大模型提供工具（MCP + Function Calling）")
    print("=" * 60)

    # 1. 通过 MCP 发现工具（tools/list），转成 OpenAI 格式
    client.initialize()
    raw_tools = client.list_tools()
    tools = [{
        "type": "function",
        "function": {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "parameters": t["function"]["parameters"],
        },
    } for t in raw_tools]
    print(f">>> 通过 MCP 拿到 {len(tools)} 个工具，已转成模型可用的 Schema")

    # 2. 循环对话：每轮由用户提问，输入 exit 结束对话
    while True:
        # 用户提问 -> 发给模型（携带工具清单）
        # 问题不固定：由用户实时输入，例如：北京今天天气怎么样？顺便告诉我现在的日期时间
        question = input("\n请输入你的问题（输入 exit 退出）：").strip()
        if question.lower() == "exit":
            print(">>> 已退出对话")
            break
        messages = [{"role": "user", "content": question}]
        print(f">>> 用户问题：{question}")
        msg = call_llm(messages, tools)                  # 首次调用模型 ⭐⭐⭐⭐⭐

        # 3. 模型返回工具调用请求（tool_calls）——注意：模型没有真的执行工具！
        tool_calls = msg.get("tool_calls") or []   # 获取回复中的 tool_calls 字段
        messages.append({                       # 模型回复要存进历史
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })
        print(f">>> 模型请求调用工具：{[tc['function']['name'] for tc in tool_calls]}")

        # 4. 真正执行工具的是谁？是 Server 进程（经 MCP tools/call）！   
        for tc in tool_calls:                   # ⭐⭐⭐⭐⭐ 若有多个工具调用，要循环执行
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")   
            result = client.call_tool(name, args)     # 经 MCP 跨进程执行  
            messages.append({                         # 结果回填给模型
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
            print(f">>> 工具 {name} 执行结果：{result}")

        # 5. 带着工具结果再问一次模型，模型组织最终答案
        final = call_llm(messages, tools)                  # 第二次调用模型 ⭐⭐⭐⭐⭐（PS:此处有些不合理，有可能是ReACT模式, 但是这里为了简单，总共只调用2次）
        print(f"\n>>> 最终回答：{final.get('content')}")


    # print("  工具不在 Agent 进程里，而在独立的 Server 进程里；")
    # print("  模型只负责'说要调哪个工具'，真正执行靠 MCP 协议跨进程完成。")


if __name__ == "__main__":
    # 用当前解释器启动 server.py（-m 不行，直接给文件路径即可）
    cmd = [sys.executable, "server.py"]    # cmd 是 [python解释器路径, "server.py"]，意思是"用当前 Python 解释器运行 server.py"。注意 "server.py" 是相对路径，需要在项目根目录下运行

    # 重要知识点：Server 进程的日志不能往 stdout 打印！
    # 因为 stdout 是协议通道，打印会把 JSON 消息弄脏。
    # （本项目 server.py 已遵守，仅在 stdin/stdout 间交换 JSON）

    c = ProtocolMCPClient(cmd)   # 创建一个 ProtocolMCPClient 实例，参数 cmd
    try:
        if "--llm" in sys.argv:   # 如果用户传了 --llm 参数，就用模式2 
            demo_with_llm(c)
        else:
            demo_manual(c)
    finally:
        c.close()

