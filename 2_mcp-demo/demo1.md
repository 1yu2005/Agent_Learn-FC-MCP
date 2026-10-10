# 第一部分：mcp-protocol-demo（原理篇，零依赖）

## 架构（就 2 个文件）

```
3_mcp-protocol-demo/
├── server.py    # MCP Server：手写 JSON-RPC + stdio，收请求、回响应
└── client.py    # MCP Client：拉起 Server 进程，发请求、收响应（把每条消息打印给你看）
```

进程关系（MCP 的本质就是两个进程说话）：

```
你运行的 client.py（进程A）
     │  stdin 管道 ──写──▶ 一行 JSON 请求        （如 tools/list）
     ▼
server.py（子进程B，由 client 拉起）
     │  stdout 管道 ──写──▶ 一行 JSON 响应
     ▼
client.py 收到响应并打印
```

## server.py（完整代码）

```python
"""【原理篇】手写 MCP Server：JSON-RPC 2.0 + stdio。

MCP 的底层其实非常简单，核心就三件事：
1. 两个进程之间用"标准输入/标准输出"管道通信（这叫 Transport，stdio 传输）；
2. 消息格式是 JSON-RPC 2.0（每条消息是一行 JSON，叫 newline-delimited JSON）；
3. 协议约定三个方法：
   - initialize  ：握手。Client 问"你是谁、支持什么能力"，Server 回答
   - tools/list  ：Client 问"你有哪些工具"，Server 返回工具清单（Schema）
   - tools/call  ：Client 说"请执行某个工具，参数是 xxx"，Server 执行后返回结果

本文件不 import 任何 mcp 包，纯标准库实现，
每一行都在还原官方 SDK 内部替你做的事情。
"""
import json
import sys
from datetime import datetime  # 给工具用：获取当前时间

# ===================== 工具定义 =====================
# 这就是"Server 提供工具"的意思：工具清单 + 执行函数
# （先定义数据，再定义函数，最后在下面注册）

_WEATHER_DB = {          # 模拟天气数据（真实项目这里换成调天气 API）
    "北京": "晴，气温 25°C",
    "上海": "多云，气温 27°C",
    "广州": "阵雨，气温 30°C",
}

# 工具 Schema 清单：告诉 Client "我有这些工具、每个工具要什么参数"
# 这个格式和 Function Calling 里发给模型的 tools 数组一模一样
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",                 # 工具名
            "description": "查询指定城市的当前天气",  # 功能描述
            "parameters": {                        # 参数结构
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 北京"}
                },
                "required": ["city"],              # 必填参数
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前系统日期与时间",
            "parameters": {"type": "object", "properties": {}},  # 无参数
        },
    },
]

# 工具执行器：工具名 -> 真正干活的函数（这就是"工具注册表"）
def _get_weather(city: str) -> str:
    return _WEATHER_DB.get(city, f"暂无 {city} 的天气数据")

def _get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

EXECUTORS = {
    "get_weather": _get_weather,
    "get_current_time": _get_current_time,
}

# ===================== 协议处理 =====================
def handle_request(request: dict) -> dict:
    """处理一条 Client 发来的 JSON-RPC 请求，返回响应

    这是整个 MCP Server 的核心：按 method 字段分发到不同逻辑。
    """
    method = request.get("method")          # 请求的方法名：initialize / tools/list / tools/call
    params = request.get("params", {})      # 请求的参数
    result = None

    if method == "initialize":
        # 握手：告诉 Client 协议版本、支持的能力、我是谁
        result = {
            "protocolVersion": "2024-11-05",      # 协议版本号
            "capabilities": {"tools": {}},        # 我支持 tools 能力
            "serverInfo": {"name": "protocol-server", "version": "1.0.0"},
        }
    elif method == "tools/list":
        # 返回工具清单（Client 拿到后可以转给模型用）
        result = {"tools": TOOL_SCHEMAS}
    elif method == "tools/call":
        # 执行工具：name 是要调的工具名，arguments 是参数 dict
        name = params.get("name")
        arguments = params.get("arguments", {})
        func = EXECUTORS.get(name)          # 从注册表取函数
        if func is None:
            text = f"错误：未注册的工具 {name}"
        else:
            try:
                text = func(**arguments)    # 把参数展开传给函数并执行
            except Exception as exc:
                text = f"工具执行失败：{exc}"
        # MCP 规定：工具结果必须包成 content 文本块列表
        result = {"content": [{"type": "text", "text": text}]}
    else:
        result = {"error": f"未知方法 {method}"}

    # 组装 JSON-RPC 响应：jsonrpc 版本 + 请求的 id（必须回同一个 id）+ 结果
    return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}

# ===================== 传输主循环（Transport） =====================
def main() -> None:
    """一直读 stdin，处理一条请求回一条响应。

    sys.stdin 是标准输入（Client 写的管道那一端），
    sys.stdout 是标准输出（Client 读的管道那一端）。
    """
    # 逐行读取 Client 发来的请求（每行一条 JSON）
    for line in sys.stdin:
        if not line.strip():
            continue                       # 跳过空行
        try:
            request = json.loads(line)             # 字符串 -> dict
            response = handle_request(request)     # 交给协议分发处理
        except Exception as exc:
            # JSON 解析失败：按 JSON-RPC 规范回错误码 -32700
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": str(exc)}}
        # 把响应写回 stdout，必须 flush（不 flush Client 那边读不到）
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
```

## client.py（完整代码）

```python
"""【原理篇】手写 MCP Client：JSON-RPC 2.0 + stdio。

Client 负责：拉起 Server 子进程 → 通过管道发请求 → 收响应。
本文件把"发送的每条请求"和"收到的每条响应"都打印出来，
跑一次就能直观看到 MCP 协议是怎么交换消息的。

两种运行模式：
    python client.py          # 模式1：手动调工具，看清协议消息
    python client.py --llm    # 模式2：接入本地大模型，看清 MCP 是怎么给 LLM 提供工具的
"""
import json
import subprocess
import sys
import urllib.request  # 模式2用：调本地 Ollama（标准库即可，无需 openai 包）

# ===================== 传输层：拉起 Server 进程 =====================
class ProtocolMCPClient:
    """手写 MCP Client：每个方法对应 MCP 协议的一个方法"""

    def __init__(self, server_cmd: list[str]):
        # 启动 Server 子进程，接好 stdin/stdout 两条管道
        # 这一步就是 Transport（stdio 传输）：两个进程通过管道说话
        self._proc = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,   # 我们往这里写，Server 从它的 stdin 读
            stdout=subprocess.PIPE,  # Server 往它的 stdout 写，我们在这里读
            text=True,
            encoding="utf-8",
        )
        self._next_id = 1            # JSON-RPC 用自增 id 对应请求和响应

    def _request(self, method: str, params: dict | None = None) -> dict:
        """发送一条 JSON-RPC 请求，并等 Server 的响应"""
        req = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            req["params"] = params
        self._next_id += 1

        # ---- 打印：让初学者看清"我们发出了什么" ----
        print(f"\n【Client 发送】{json.dumps(req, ensure_ascii=False)}")

        # 写方向：把请求写成一行 JSON，写入 Server 的 stdin
        self._proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

        # 读方向：从 Server 的 stdout 读一行 JSON（阻塞等待 Server 回复）
        line = self._proc.stdout.readline()
        response = json.loads(line)

        # ---- 打印：让初学者看清"Server 回了什么" ----
        print(f"【Server 响应】{line.strip()}")
        return response

    # ===== 下面三个方法就是 MCP 协议的核心方法 =====

    def initialize(self) -> dict:
        """协议方法 initialize：握手，确认协议版本与能力"""
        return self._request("initialize")

    def list_tools(self) -> list[dict]:
        """协议方法 tools/list：问 Server 有哪些工具，拿回 Schema 清单"""
        resp = self._request("tools/list")
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        """协议方法 tools/call：请 Server 执行某个工具，返回结果文本"""
        resp = self._request("tools/call", {"name": name, "arguments": arguments})
        content = resp.get("result", {}).get("content", [])
        # MCP 结果结构：content 是文本块列表，逐个取 text 拼起来
        return "\n".join(item.get("text", "") for item in content)

    def close(self) -> None:
        """收尾：关掉 Server 子进程"""
        self._proc.terminate()

# ===================== 模式1：手动调工具（先跑这个！） =====================
def demo_manual(client: ProtocolMCPClient) -> None:
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
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]


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

    # 2. 用户提问 -> 发给模型（携带工具清单）
    question = "北京今天天气怎么样？顺便告诉我现在的日期时间"
    messages = [{"role": "user", "content": question}]
    print(f">>> 用户问题：{question}")
    msg = call_llm(messages, tools)

    # 3. 模型返回工具调用请求（tool_calls）——注意：模型没有真的执行工具！
    tool_calls = msg.get("tool_calls") or []
    messages.append({                       # 模型回复要存进历史
        "role": "assistant",
        "content": msg.get("content") or "",
        "tool_calls": tool_calls,
    })
    print(f">>> 模型请求调用工具：{[tc['function']['name'] for tc in tool_calls]}")

    # 4. 真正执行工具的是谁？是 Server 进程（经 MCP tools/call）！
    for tc in tool_calls:
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
    final = call_llm(messages, tools)
    print(f"\n>>> 最终回答：{final.get('content')}")

    print("\n到这里你应该理解了 MCP 的作用：")
    print("  工具不在 Agent 进程里，而在独立的 Server 进程里；")
    print("  模型只负责'说要调哪个工具'，真正执行靠 MCP 协议跨进程完成。")


if __name__ == "__main__":
    # 用当前解释器启动 server.py（-m 不行，直接给文件路径即可）
    cmd = [sys.executable, "server.py"]

    # 重要知识点：Server 进程的日志不能往 stdout 打印！
    # 因为 stdout 是协议通道，打印会把 JSON 消息弄脏。
    # （本项目 server.py 已遵守，仅在 stdin/stdout 间交换 JSON）

    c = ProtocolMCPClient(cmd)
    try:
        if "--llm" in sys.argv:
            demo_with_llm(c)
        else:
            demo_manual(c)
    finally:
        c.close()
```

## 运行与预期输出（模式1）

```bash
cd D:\Agent\AI Agent 面试全攻略\code\04_工具调用\3_mcp-protocol-demo
python client.py
============================================================
模式1：手动调用 MCP 协议方法，观察消息流动
============================================================

【Client 发送】{"jsonrpc": "2.0", "id": 1, "method": "initialize"}
【Server 响应】{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "protocol-server", "version": "1.0.0"}}}

【Client 发送】{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
【Server 响应】{"jsonrpc": "2.0", "id": 2, "result": {"tools": [...]}}
...
```

看完这段输出，MCP 的"工作流程"就具象了：**id 对应、method 分发、stdio 传输**。





# 补充：模型返回的格式

```python
def call_llm(messages: list[dict], tools: list[dict]) -> dict:
    """用 urllib 调本地 Ollama（OpenAI 兼容接口），返回模型的回复"""
    body = {"model": MODEL, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]
```

下面给出**完整响应体**（`resp.read()` 解析后的 `data`）的结构，字段解释直接写在里面。因为标准 JSON 不支持注释，这里用的是 **JSONC 风格**（`//` 注释），阅读时可以自行删掉注释。

```jsonc
{
  // ===== 顶层字段（OpenAI Chat Completions 规范）=====
  "id": "chatcmpl-123",              // 本次补全的唯一 ID
  "object": "chat.completion",       // 对象类型，固定值
  "created": 1728374400,             // Unix 时间戳（秒）
  "model": "qwen2.5:7b",             // 实际使用的模型名

  // ===== 候选回复列表 =====
  // 单线程时通常只有 1 个元素，取 [0] 即可
  "choices": [
    {
      "index": 0,                    // 该候选在列表中的序号
      "finish_reason": "stop",       // 结束原因：stop=自然结束 / tool_calls=要调工具 / length=超长截断
      "logprobs": null,              // 对数概率信息，一般不用，常为 null

      // ===== 你代码里最终返回的 message =====
      "message": {
        "role": "assistant",         // 角色，固定为 assistant

        // --- 情况 A：纯文本回复时，content 是字符串 ---
        // --- 情况 B：工具调用时，content 通常为 null 或 "" ---
        "content": "北京的天气是晴，25°C。",

        // --- 可选：推理模型（如 deepseek-r1）的思考过程，普通模型没有此字段 ---
        "reasoning_content": null,

        // --- 可选：仅当模型决定调用工具时出现；无工具调用时该字段不存在或为 null ---
        "tool_calls": [
          {
            "id": "call_abc123",     // 本次工具调用的唯一 ID，回传结果时必须对应
            "type": "function",      // 调用类型，目前基本都是 "function"
            "function": {
              "name": "get_weather", // 要调用的工具/函数名，必须与 tools 里定义的一致

              // ★ 注意：arguments 是「JSON 字符串」，不是对象
              // 需要 json.loads(...) 解析成 dict 才能用
              // 有些 Ollama 版本可能直接给对象，写代码时要兼容
              "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
            }
          }
          // ... 可能有多项，表示模型想并行调用多个工具
        ]
      }
    }
  ],

  // ===== token 用量统计（部分后端会返回，Ollama 兼容层不一定有）=====
  "usage": {
    "prompt_tokens": 42,             // 输入消息消耗的 token 数
    "completion_tokens": 18,         // 输出消耗的 token 数
    "total_tokens": 60                // 合计
  }
}
```

---

## 你代码真正拿到的东西

你的代码最后：

```python
return data["choices"][0]["message"]
```

所以返回给调用方的其实是上面那一大块里的 **`message` 对象**：

```jsonc
// 情形一：普通文本
{
  "role": "assistant",
  "content": "北京的天气是晴，25°C。",
  "reasoning_content": null
}

// 情形二：要调用工具
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
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
```

---

## 字段速查表

| 字段                              | 类型         | 说明                                                |
| --------------------------------- | ------------ | --------------------------------------------------- |
| `id`                              | string       | 本次补全的全局唯一 ID                               |
| `object`                          | string       | 固定 `"chat.completion"`                            |
| `created`                         | int          | 创建时间戳（秒）                                    |
| `model`                           | string       | 实际响应的模型名                                    |
| `choices`                         | array        | 候选回复列表，取 `[0]`                              |
| `choices[].index`                 | int          | 候选序号                                            |
| `choices[].finish_reason`         | string       | `stop` / `tool_calls` / `length` / `content_filter` |
| `choices[].logprobs`              | object\|null | 概率信息，通常忽略                                  |
| `message.role`                    | string       | 固定 `"assistant"`                                  |
| `message.content`                 | string\|null | 文本内容；调工具时为 null                           |
| `message.reasoning_content`       | string\|null | 推理过程（可选，非所有模型都有）                    |
| `message.tool_calls`              | array\|缺省  | 工具调用列表，无则不出现                            |
| `tool_calls[].id`                 | string       | 调用 ID，回传 `role:"tool"` 消息时要对应            |
| `tool_calls[].type`               | string       | 目前恒为 `"function"`                               |
| `tool_calls[].function.name`      | string       | 函数名                                              |
| `tool_calls[].function.arguments` | string       | **JSON 字符串**，需自行 `json.loads`                |
| `usage.prompt_tokens`             | int          | 输入 token 数（可选）                               |
| `usage.completion_tokens`         | int          | 输出 token 数（可选）                               |
| `usage.total_tokens`              | int          | 总 token 数（可选）                                 |

---

## 两个容易踩的坑

1. **`arguments` 是字符串不是对象** —— 一定要 `json.loads(tc["function"]["arguments"])`，Ollama 某些版本可能给成对象，用 `isinstance(arguments, str)` 判断一下更稳。
2. **`finish_reason == "tool_calls"` 时 `content` 可能是 null** —— 别直接 `msg["content"]` 去 `print` 或当字符串处理，容易报 `NoneType` 错误。