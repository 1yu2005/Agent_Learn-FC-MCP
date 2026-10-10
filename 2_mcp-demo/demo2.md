---

# 第二部分：mcp-sdk-demo（工程篇 · 完整版）

## 一、架构

```
demo2_工程篇/
├── .env.example                  # 环境变量模板（LLM 配置，API 无需密钥）
├── .gitignore
├── requirements.txt              # 第三方依赖
├── server/                       # MCP Server 层（独立进程，对外提供工具）
│   ├── __init__.py
│   ├── weather_server.py         # Server A：天气/计算/时间（本地工具）
│   └── xxapi_server.py           # Server B：4 个小小API外部工具 + 骰子
└── client/                       # Host + MCP Client 层
    ├── __init__.py
    ├── config.py                 # 配置读取
    ├── logging_config.py         # 日志
    ├── llm.py                    # 对接本地 Ollama
    ├── mcp_client.py             # 官方 SDK：连接多 Server、聚合工具
    ├── agent.py                  # Agent 主循环（Function Calling 编排）
    └── main.py                   # 程序入口
```

角色对应（对照原理篇理解）：

| 层级   | 原理篇手写                   | 工程篇                           | 职责                        |
| ------ | ---------------------------- | -------------------------------- | --------------------------- |
| Server | `server.py` 的 if/elif 分发  | `FastMCP` + `@mcp.tool()`        | 提供工具，等 Client 来调    |
| Client | `ProtocolMCPClient._request` | `stdio_client` + `ClientSession` | 连接 Server、发现与调用工具 |
| Host   | `client.py` 主流程           | `agent.py`                       | 编排 LLM 与工具，完成问答   |

## 二、文件与代码

### 1. requirements.txt

```txt
# MCP 官方 Python SDK（协议层）
mcp>=1.2.0

# OpenAI 兼容客户端（对接本地 Ollama）
openai>=1.30.0

# 外部 API 请求（小小API）
requests>=2.31.0

# 读取 .env 配置
python-dotenv>=1.0.0
```

### 2. .env.example

```ini
# ===== LLM 配置（本地 Ollama OpenAI 兼容端点）=====
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL_NAME=qwen-8B-finetune-int4:latest
OPENAI_API_KEY=sk-xxx

# ===== 小小API（xxapi.cn）=====
# 免费接口，无需密钥；仅需指定域名（已按官方文档默认填好，一般不用改）
XXAPI_BASE=https://v2.xxapi.cn

# ===== MCP Server 启动命令 =====
# 留空时默认用当前 Python 解释器，避免调用到系统 PATH 里缺 mcp 包的其他 Python
MCP_SERVER_COMMAND=

# ===== Agent 配置 =====
MAX_ITERATIONS=5
REQUEST_TIMEOUT=60
```

### 3. .gitignore

```gitignore
.env
venv/
.idea/
__pycache__/
*.pyc
```

### 4. server/__init__.py

```python
"""MCP Server 包：以独立进程方式提供工具能力"""
```

### 5. server/weather_server.py

```python
"""天气 + 本地工具 MCP Server（FastMCP 工程实践）。

FastMCP 自动完成原理篇 server.py 手写的三件事：
- 协议分发（initialize / tools/list / tools/call）
- 工具 Schema 生成（从函数签名和 docstring 自动推导）
- stdio 传输主循环（stdin 读请求、stdout 写响应）

我们只需要用 @mcp.tool() 声明工具即可。
"""
import logging
from datetime import datetime

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.server.weather")

# 数据源层：真实项目里替换成天气 API 调用
_WEATHER_DB = {
    "北京": "晴，气温 25°C，空气质量 良",
    "上海": "多云，气温 27°C，空气质量 优",
    "广州": "阵雨，气温 30°C，空气质量 良",
    "深圳": "雷阵雨，气温 29°C，空气质量 良",
    "杭州": "阴，气温 26°C，空气质量 优",
}
_AQI_DB = {"北京": 75, "上海": 40, "广州": 60, "深圳": 55, "杭州": 48}

mcp = FastMCP("weather-server")  # 创建 Server（名字会出现在 initialize 的 serverInfo）

@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。当用户询问某城市天气、气温时调用本工具。"""
    try:
        return _WEATHER_DB.get(city, f"暂无 {city} 的天气数据")
    except Exception as exc:
        logger.exception("get_weather 执行异常")
        return f"天气查询失败：{exc}"

@mcp.tool()
def get_air_quality(city: str) -> str:
    """查询指定城市的空气质量指数（AQI）。当用户询问空气、污染、雾霾时调用本工具。"""
    try:
        aqi = _AQI_DB.get(city)
        if aqi is None:
            return f"暂无 {city} 的空气质量数据"
        level = "优" if aqi <= 50 else "良" if aqi <= 100 else "轻度污染"
        return f"{city} AQI 为 {aqi}，等级：{level}"
    except Exception as exc:
        logger.exception("get_air_quality 执行异常")
        return f"空气质量查询失败：{exc}"

@mcp.tool()
def calculate(expression: str) -> str:
    """计算数学表达式，支持 + - * / 与括号。当用户要求计算时调用本工具。"""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "参数错误：表达式包含非法字符"
    try:
        result = eval(expression)  # 仅演示：已做白名单过滤；生产请用 ast 或专用解析器
        return f"{expression} = {result}"
    except Exception as exc:
        return f"计算失败：{exc}"

@mcp.tool()
def get_current_time() -> str:
    """获取当前系统日期与时间。当用户询问现在几点、今天日期时调用本工具。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 与原理篇的 stdin/stdout 主循环是同一件事
```

### 6. server/xxapi_server.py

```python
"""小小API（xxapi.cn）外部工具 MCP Server（FastMCP）。

展示：MCP 工具内部对接真实 HTTP 接口。
本 Server 全部工具经 _call() 统一走小小API，接口已实测可用：
    https://v2.xxapi.cn/api/englishwords?word=hello      （英语单词详解）
    https://v2.xxapi.cn/api/dujitang                     （毒鸡汤）
    https://v2.xxapi.cn/api/phonejixiong?phone=...       （手机号码吉凶）
    https://v2.xxapi.cn/api/history                      （历史上的今天）

小小API 统一返回：{"code": 200, "msg": "数据请求成功", "data": ...}
data 可能是字符串（毒鸡汤）、对象（单词/吉凶）或数组（历史事件），
统一 JSON 序列化后作为文本返回给模型。
"""
import json
import logging
import os
import random

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.server.xxapi")

load_dotenv()  # Server 进程在项目根目录启动，可读到 .env
XXAPI_BASE = os.getenv("XXAPI_BASE", "https://v2.xxapi.cn").rstrip("/")
# 官方文档建议携带该 UA，避免被限流
HEADERS = {"User-Agent": "xiaoxiaoapi/1.0.0 (https://xxapi.cn)"}

mcp = FastMCP("xxapi-server")

def _call(endpoint: str, params: dict) -> str:
    """通用封装：请求小小API接口，把 data 转成模型可读文本"""
    try:
        resp = requests.get(
            f"{XXAPI_BASE}/{endpoint}", params=params, headers=HEADERS, timeout=10
        )
        data = resp.json()
    except Exception as exc:
        logger.exception("API 请求异常")
        return f"API 请求失败：{exc}"
    if data.get("code") != 200:
        return f"API 错误：{data.get('msg')}"
    return json.dumps(data.get("data"), ensure_ascii=False)

@mcp.tool()
def get_word_detail(word: str) -> str:
    """查询英语单词的详细释义（短语/音标/翻译/例句）。当用户询问英文单词意思时调用本工具。"""
    if not word.isalpha():
        return "参数错误：word 必须是英文字母组成的单词"
    return _call("englishwords", {"word": word})

@mcp.tool()
def get_dujitang() -> str:
    """获取一条随机毒鸡汤语录。当用户想要毒鸡汤、扎心语录时调用本工具。"""
    return _call("dujitang", {})

@mcp.tool()
def get_phone_fortune(phone: str) -> str:
    """分析手机号码的吉凶。当用户询问手机号吉凶、运势时调用本工具。"""
    if not (phone.isdigit() and len(phone) == 11):
        return "参数错误：phone 必须是 11 位数字手机号"
    return _call("phonejixiong", {"phone": phone})

@mcp.tool()
def get_today_history() -> str:
    """获取今天发生的历史事件列表。当用户询问历史上的今天时调用本工具。"""
    return _call("history", {})

@mcp.tool()
def roll_dice(sides: int = 6) -> str:
    """掷一个骰子返回随机点数（本地自写工具，不经外部 API）。当用户要求掷骰子、随机数时调用本工具。"""
    if sides < 2:
        return "参数错误：sides 至少为 2"
    return f"掷出了 {random.randint(1, sides)}（{sides} 面骰子）"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 7. client/__init__.py

```python
"""MCP Client + Host 包：连接 Server、编排 LLM 完成问答"""
```

### 8. client/config.py

```python
"""配置加载：统一从 .env / 环境变量读取，禁止散落硬编码"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # 从当前工作目录加载 .env（必须在项目根目录运行）

def get_config() -> dict:
    """集中返回运行所需配置；换云端 / 换模型只改 .env，代码零改动"""
    return {
        "base_url": os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
        "model": os.getenv("OPENAI_MODEL_NAME", "qwen-8B-finetune-int4:latest"),
        "api_key": os.getenv("OPENAI_API_KEY", "sk-xxx"),
        # MCP Server 启动命令：默认当前解释器，规避 PATH 中其他 Python 缺包
        "server_command": os.getenv("MCP_SERVER_COMMAND", "").strip() or sys.executable,
        "max_iterations": int(os.getenv("MAX_ITERATIONS", "5")),
        "timeout": float(os.getenv("REQUEST_TIMEOUT", "60")),
    }
```

### 9. client/logging_config.py

```python
"""日志配置：统一格式与级别"""
import logging

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
```

### 10. client/llm.py

```python
"""LLM 调用层：封装 OpenAI 兼容接口，返回统一结构供 Agent 编排"""
from openai import OpenAI

from .config import get_config

_cfg = get_config()
_client = OpenAI(
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

    resp = _client.chat.completions.create(**kwargs)
    choice = resp.choices[0]

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
```

### 11. client/mcp_client.py

```python
"""MCP Client 层（官方 SDK）：连接多个 Server，发现并聚合工具。

对应 MCP 架构图中的 Client 层：与每个 Server 建立会话，
把各 Server 暴露的工具统一提供给上层 Host（Agent）。
原理篇 client.py 的 _request("tools/list") 在这里就是 session.list_tools()。
"""
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPToolClient:
    """对单个 MCP Server 的客户端封装（stdio 传输）"""

    def __init__(self, command: str, args: list[str]):
        # StdioServerParameters：配置如何拉起 Server 子进程（对应原理篇 subprocess.Popen）
        self._params = StdioServerParameters(command=command, args=args)

    async def list_tools(self) -> list[dict]:
        """协议方法 tools/list：发现工具，转换为 OpenAI Function Calling 格式"""
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()           # 握手（原理篇的 initialize）
                tools = await session.list_tools()   # 协议方法 tools/list
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema,  # MCP Schema → FC Schema
                        },
                    }
                    for t in tools.tools
                ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """协议方法 tools/call：调用 Server 侧工具，返回文本结果（供回填模型）"""
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)  # 协议方法 tools/call
                parts = [item.text for item in result.content if hasattr(item, "text")]
                return "\n".join(parts) if parts else str(result)

class MCPClientManager:
    """多 Server 聚合管理器：维护 工具名 → Server 的归属路由"""

    def __init__(self, servers: list[dict]):
        self._clients = {
            s["name"]: MCPToolClient(s["command"], s["args"]) for s in servers
        }
        self._tool_owner: dict[str, str] = {}   # 工具名 -> Server 名

    async def list_all_tools(self) -> list[dict]:
        """聚合所有 Server 的工具，并记录每个工具的归属 Server"""
        merged: list[dict] = []
        for server_name, client in self._clients.items():
            for tool in await client.list_tools():
                tool_name = tool["function"]["name"]
                self._tool_owner[tool_name] = server_name
                merged.append(tool)
        return merged

    async def call_tool(self, name: str, arguments: dict) -> str:
        """按路由表把工具调用分发到正确的 Server"""
        owner = self._tool_owner.get(name)
        if owner is None:
            return f"错误：未知工具 {name}"
        return await self._clients[owner].call_tool(name, arguments)
```

### 12. client/agent.py

```python
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
```

### 13. client/main.py

```python
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
```

## 三、运行步骤

```bash
cd D:\Agent\AI Agent 面试全攻略\code\04_工具调用\4_mcp-sdk-demo
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # 无需填密钥（小小API免费），只需确认 Ollama 在跑
ollama list                   # 确认 qwen-8B-finetune-int4:latest 存在
python -m client.main
```

试问：`北京天气怎么样`、`hello 的英文释义`、`来碗毒鸡汤`、`历史上的今天`、`13800138000 吉凶`、`掷个骰子`。

## 四、API 调用核对表（全部已实测）

| 工具函数            | 请求                | 参数                  | 返回 data 类型 |
| ------------------- | ------------------- | --------------------- | -------------- |
| `get_word_detail`   | `/api/englishwords` | `word`（必填）        | 对象           |
| `get_dujitang`      | `/api/dujitang`     | 无                    | 字符串         |
| `get_phone_fortune` | `/api/phonejixiong` | `phone`（必填，11位） | 对象           |
| `get_today_history` | `/api/history`      | 无                    | 字符串数组     |



# Python 装饰器详解

装饰器（Decorator）是 Python 中非常强大且常用的语法特性，它允许==在不修改原函数代码的前提下，为函数**动态增加功能**==。理解装饰器需要先掌握三个前置知识：**函数是一等对象**、**闭包**、**函数作为参数/返回值**。

---

## 一、前置知识

### 1. 函数是一等对象

在 Python 中，函数也是对象，可以：
- 赋值给变量
- 作为参数传递
- 作为返回值
- 存入容器

```python
def greet(name):
    return f"Hello, {name}"

f = greet          # 赋值
print(f("Tom"))    # Hello, Tom

def call(func, arg):
    return func(arg)

print(call(greet, "Jerry"))  # Hello, Jerry
```

### 2. 闭包（Closure）

==闭包 = **内层函数** + **外层函数的变量**环境。==

```python
def outer(msg):
    def inner():
        print(msg)   # inner 捕获了 outer 的 msg
    return inner

f = outer("hi")
f()   # hi
```

==闭包是装饰器能"记住"原函数的关键。==

**闭包**是指一个函数，连同它定义时所处的作用域（环境）一起被保存下来。即使外层函数已经执行完毕，内层函数依然可以访问外层函数中的变量。

简单说：==**（内部）函数 + 它记住的外部变量 = 闭包。**==

例如 Python：

```python
def outer(x):
    def inner(y):
        return x + y
    return inner

add5 = outer(5)   # outer 已执行完，但 x=5 被记住了
print(add5(3))    # 输出 8
```

关键点：
- **内层函数引用了外层函数的变量**。
- **外层函数返回内层函数**后，这些变量不会被销毁，而是被闭包“捕获”保存。
- 常用于回调、装饰器、状态保持等场景。

---

## 二、最简单的装饰器

需求：给函数加上"执行前后打印日志"的功能，但不想改动原函数。

```python
def log_decorator(func):
    def wrapper(*args, **kwargs):
        print(f"[LOG] 调用 {func.__name__}")
        result = func(*args, **kwargs)
        print(f"[LOG] 结束 {func.__name__}")
        return result
    return wrapper

@log_decorator
def add(a, b):
    return a + b

print(add(2, 3))
```

输出：

```
[LOG] 调用 add
[LOG] 结束 add
5
```

### ==语法糖 `@` 的本质==

```python
@log_decorator
def add(a, b): ...
```

**完全等价于**： ⭐⭐⭐⭐⭐  即 函数作为另外一个函数的参数传递

```python
def add(a, b): ...
add = log_decorator(add)
```

也就是说，`@` 只是把下面的函数对象传给装饰器，并把返回值重新赋给同名变量。

### 为什么用 `*args, **kwargs`？

因为 wrapper 需要兼容任意签名的被装饰函数，避免参数丢失。

---

## 三、`functools.wraps` —— 保留原函数元信息

用上面的写法会遇到一个问题：

```python
print(add.__name__)   # wrapper  ← 被覆盖了
print(add.__doc__)    # None
```

原函数的 `__name__`、`__doc__`、`__module__` 等元数据被 wrapper 覆盖。解决办法是使用 `functools.wraps`：

```python
from functools import wraps

def log_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[LOG] 调用 {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

==**写装饰器时几乎都要加 `@wraps(func)`。**==

---

## 四、带参数的装饰器

==如果装饰器本身需要接收参数（例如自定义日志前缀），就再套一层函数：==

```python
from functools import wraps

def log_with(prefix):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"[{prefix}] 调用 {func.__name__}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

@log_with("DEBUG")
def add(a, b):
    return a + b

add(1, 2)
# [DEBUG] 调用 add
```

### ==三层结构口诀== ⭐⭐⭐⭐⭐

```
最外层：接收装饰器参数
中间层：接收被装饰的函数
最内层：接收调用时的实参
```

- 无参装饰器：2 层
- 带参装饰器：3 层

---

## 五、类装饰器

### 1. 用类实现装饰器

```python
class Counter:
    def __init__(self, func):
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"第 {self.count} 次调用")
        return self.func(*args, **kwargs)

@Counter
def say(msg):
    print(msg)

say("hi")
say("hello")
```

要点：`__init__` 接收函数，`__call__` 让实例可被调用。

### 2. 装饰类（而不是函数）

装饰器也可以修饰整个类：

```python
def add_repr(cls):
    cls.__repr__ = lambda self: f"<{cls.__name__}>"
    return cls

@add_repr
class Foo:
    pass

print(Foo())   # <Foo>
```

---

## 六、多个装饰器叠加

```python
@A
@B
@C
def f(): ...
```

等价于：

```python
f = A(B(C(f)))
```

**执行顺序：装饰时从下往上（C → B → A），调用时从上往下（A → B → C）。**

示例：

```python
def d1(func):
    def w(*a, **k):
        print("d1 进入"); r = func(*a, **k); print("d1 退出"); return r
    return w

def d2(func):
    def w(*a, **k):
        print("d2 进入"); r = func(*a, **k); print("d2 退出"); return r
    return w

@d1
@d2
def hello():
    print("hello")

hello()
```

输出：

```
d1 进入
d2 进入
hello
d2 退出
d1 退出
```

---

## 七、常见应用场景

| 场景                  | 说明                      |
| --------------------- | ------------------------- |
| **日志记录**          | 记录函数调用、参数、耗时  |
| **性能计时**          | `time.time()` 包裹        |
| **权限校验**          | Web 框架中检查登录/角色   |
| **缓存**              | `functools.lru_cache`     |
| **重试机制**          | 失败自动重试              |
| **参数校验/类型检查** | 检查传入参数              |
| **注册函数**          | Flask 路由 `@app.route()` |
| **事务管理**          | `@transactional`          |

### 示例：计时装饰器

```python
import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        cost = time.perf_counter() - start
        print(f"{func.__name__} 耗时 {cost:.4f}s")
        return result
    return wrapper

@timer
def slow():
    time.sleep(1)

slow()
```

### 示例：内置的 `lru_cache`

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n-1) + fib(n-2)

print(fib(100))  # 瞬间完成
```

---

## 八、进阶技巧

### 1. 保留函数签名 (`functools.wraps` 已做大部分)

若想 `inspect.signature` 也正确，`@wraps` 已足够。

### 2. 类装饰器 + `__get__` 实现描述符

可以让装饰器在方法上也能正常工作（例如类方法、实例方法）。

### 3. 用 `contextlib.ContextDecorator` 同时支持上下文和装饰

```python
from contextlib import ContextDecorator

class mycontext(ContextDecorator):
    def __enter__(self):
        print("enter"); return self
    def __exit__(self, *exc):
        print("exit"); return False

@mycontext()
def do():
    print("doing")

do()
```

### 4. 装饰器注册表（Flask 风格）

```python
routes = {}

def route(path):
    def deco(func):
        routes[path] = func
        return func
    return deco

@route("/home")
def home(): ...

@route("/about")
def about(): ...

print(routes)  # {'/home': <function home>, '/about': <function about>}
```

---

## 九、常见坑

1. **忘记 `@wraps`** → 函数元信息丢失，调试困难。
2. **忘记 `return func(...)`** → 被装饰函数返回值变成 `None`。
3. **混淆三层结构** → 带参装饰器需三层嵌套。
4. **在 wrapper 里用位置参数硬编码** → 用 `*args, **kwargs` 通吃。
5. **装饰器立即执行 vs 调用时执行**：
   - 装饰器函数体在**导入/定义**时执行一次
   - wrapper 内的代码在**调用时**执行
6. **多个装饰器顺序**记错。

---

## 十、一张图总结

```
@decorator
def func(...): ...

等价于

func = decorator(func)

其中 decorator(func) 返回 wrapper
调用 func(...) 实际调用 wrapper(...)
wrapper 内部调用原 func(...)
```

---

## 十一、练习题

**1. 写一个 `@repeat(n)` 装饰器，让函数执行 n 次。**

```python
def repeat(n):
    def deco(func):
        @wraps(func)
        def wrapper(*a, **k):
            for _ in range(n):
                func(*a, **k)
        return wrapper
    return deco

@repeat(3)
def hi():
    print("hi")

hi()   # 打印三次 hi
```

**2. 写一个 `@retry(times=3)`，失败自动重试。**

**3. 写一个 `@cache` 装饰器，缓存函数结果（键用参数）。**

---

掌握装饰器的关键：==**函数是对象 → 闭包能记住外层变量 → `@` 是语法糖**==。把这三句话吃透，再加上 `functools.wraps` 的习惯，就基本无敌了。

