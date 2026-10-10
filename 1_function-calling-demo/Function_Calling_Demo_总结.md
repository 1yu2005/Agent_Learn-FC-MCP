# Function Calling Demo 总结

> 项目： 1_function-calling-demo
> 环境：Python 3.12.10 + venv 虚拟环境，本地 Ollama 模型 qwen-8B-finetune-int4:latest（5.0 GB），实测支持 Function Calling
> 协议：OpenAI 兼容接口（http://localhost:11434/v1）

---

## 一、操作步骤（含全部代码及注释）

### 1. 运行步骤

```bash
# 创建项目目录
mkdir 1_function-calling-demo
cd 1_function-calling-demo

# 创建虚拟环境并激活（Windows）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install openai python-dotenv

# 生成本地配置（默认值即本机 Ollama，无需改）  要将模板中的值改成自己的值
copy .env.example .env

# 最后启动
python -m src.main
```

### 2. 项目结构

```
1_function-calling-demo/
├── .env.example          # 环境变量模板（提交到仓库）     copy .env.example .env
├── .env                  # 实际配置（从模板复制，不提交）
├── requirements.txt      # 依赖清单
├── src/
│   ├── __init__.py
│   ├── config.py         # 读取 .env 配置
│   ├── llm.py            # 大模型调用封装（OpenAI 兼容协议）
│   ├── agent.py          # Agent 主循环
│   ├── main.py           # 入口
│   └── tools/
│       ├── __init__.py
│       ├── weather.py    # 天气工具（模拟实现）
│       └── registry.py   # 工具注册表（插件模式）
```

### 3. 各文件代码

#### requirements.txt

```
openai
python-dotenv
```

#### .env.example

```ini
# 本地 Ollama 的 OpenAI 兼容接口地址
OLLAMA_BASE_URL=http://localhost:11434/v1

# 使用的本地模型名称（需先 ollama pull）  要确保ollama在运行中，同时ollama list中有该模型
OLLAMA_MODEL=qwen-8B-finetune-int4:latest

# Agent 最大迭代次数，防止模型反复调工具造成死循环
MAX_ITERATIONS=10
```

> 复制命令：Windows 的 cmd 下用 `copy .env.example .env`（powershell用 `Copy-Item`）。

#### src/config.py

```python
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件（必须在根目录运行，见第三节说明）
load_dotenv()

# OpenAI 兼容接口地址，默认指向本地 Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# 模型名称，默认使用本地微调好的 Qwen 模型
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen-8B-finetune-int4:latest")

# 最大迭代次数，兜底防止死循环
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
```

#### src/llm.py

```python
from openai import OpenAI
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

# 创建 OpenAI 兼容客户端，只需改 base_url 即可切换到任意 OpenAI 兼容服务
client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

def chat(messages, tools=None):
    """
    与模型对话。

    参数:
        messages: 对话消息列表（OpenAI 格式）
        tools: 工具声明列表（JSON Schema），为 None 时不启用工具调用

    返回:
        统一格式的 dict:
        {
            "content": 模型回复文本（无工具调用时为最终回答）,
            "tool_calls": [
                {"id": "...", "type": "function",
                 "function": {"name": "get_weather", "arguments": '{"city": "北京"}'}}
            ]  # 无工具调用时为 []
        }
    """
    # 构造请求参数，仅在传入 tools 时附加
    kwargs = {"model": OLLAMA_MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools

    # 调用模型
    resp = client.chat.completions.create(**kwargs)

    # 取出首个 choice（对话场景通常只看第一个）
    choice = resp.choices[0]

    # 标准化返回结果
    return {
        "content": choice.message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": tc.type,
                # 注意：function 是嵌套对象，不是字符串
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in (choice.message.tool_calls or [])
        ],
    }
```

#### src/tools/weather.py

```python
# 模拟天气数据：城市 -> 天气描述
WEATHER_MAP = {"北京": "晴 25°C", "上海": "多云 28°C", "广州": "阵雨 30°C"}
def get_weather(city: str) -> str:
    """
    查询指定城市的天气。

    参数:
        city: 城市名称

    返回:
        该城市的天气描述字符串；未收录的城市给出提示。
    """
    return WEATHER_MAP.get(city, f"{city} 天气数据暂缺")
```

#### src/tools/registry.py

```python
import json
from .weather import get_weather

# 工具声明列表（JSON Schema，注册给模型看）
# 模型看到这份声明才知道有哪些工具可用、需要传什么参数
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如：北京",
                    }
                },
                "required": ["city"],
            },
        },
    }
]

# 工具执行器注册表：工具名 -> 实际函数
# 新增工具只需在此注册，即"插件模式"
_EXECUTORS = {
    "get_weather": get_weather,
}


def execute_tool(name: str, arguments_json: str) -> str:
    """
    执行工具。

    参数:
        name: 工具名
        arguments_json: 模型生成的参数字符串（JSON 格式）

    返回:
        工具执行结果字符串
    """
    # 从注册表取出执行器；未注册的工具返回错误兜底
    func = _EXECUTORS.get(name)
    if func is None:
        return f"错误：未注册的工具 {name}"

    # 解析模型传来的参数（JSON 字符串 -> dict）
    args = json.loads(arguments_json)
    return func(**args)
```

#### src/agent.py

```python
from .config import MAX_ITERATIONS
from .llm import chat
from .tools.registry import TOOL_SCHEMAS, execute_tool


def run_agent(user_question: str) -> str:
    """
    Agent 主循环：
    模型派单 -> 平台执行工具 -> 结果回填 -> 模型作答

    参数:
        user_question: 用户提问

    返回:
        最终回答文本
    """
    # 对话消息列表，用户问题作为第一条
    messages = [{"role": "user", "content": user_question}]

    # 迭代上限，防止模型反复调工具形成死循环
    for _ in range(MAX_ITERATIONS):
        # 1. 请求模型（带工具声明，允许模型派单）
        result = chat(messages, tools=TOOL_SCHEMAS)

        # 2. 把模型的回复追加进消息列表
        messages.append(
            {
                "role": "assistant",
                "content": result["content"],
                # 有工具调用时原样带回，供下一步执行
                "tool_calls": result["tool_calls"] or None,
            }
        )

        # 3. 没有工具调用 -> 模型已给出最终答案，直接返回
        if not result["tool_calls"]:
            return result["content"]

        # 4. 逐个执行模型派发的工具，结果以 tool 角色回填
        for tc in result["tool_calls"]:
            name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            output = execute_tool(name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": output,
                }
            )

        # 5. 回到循环顶部，让模型基于工具结果继续作答

    # 超过最大迭代次数仍未结束，兜底返回
    return "已达最大迭代次数，停止。"
```

#### src/main.py

```python
from src.agent import run_agent


def main():
    """交互式命令行入口。"""
    print("Function Calling Demo（输入 exit 退出）")
    while True:
        # 读取用户输入
        question = input("\n请输入问题：").strip()
        if question.lower() == "exit":
            break

        # 交给 Agent 处理并打印结果
        answer = run_agent(question)
        print(f"\nAgent: {answer}")


if __name__ == "__main__":
    main()
```

#### src/__init__.py 与 src/tools/__init__.py

```python
# 空文件，标记目录为 Python 包，使 src 内部可以使用相对导入
```

### 4. 运行

```bash
# 必须在项目根目录下运行（原因见第三节）
python -m src.main
```

### 5. 验证结果

输入"北京今天天气怎么样？"：

```
Agent: 北京今天天气晴朗，气温25°C，适合外出活动哦！
```

完整链路：模型识别意图并派单 `get_weather` → 平台执行工具返回数据 → 结果回填模型 → 模型组织语言作答。

---

## 二、为什么用 `.env.example` 而不直接创建 `.env`

1. **安全**：`.env` 里将来会放 API Key 等敏感信息，若被提交到 Git 仓库会泄露。`.env.example` 只放键名和示例值，可安全入库。
2. **协作**：团队其他人 clone 仓库后，看 `.env.example` 就知道需要配置哪些变量，复制一份改名即可，无需追问。
3. **规范**：`.gitignore` 里忽略 `.env`、保留 `.env.example`，是业界通用做法（环境无关、可移植）。

---

## 三、为什么必须在项目根目录下运行

1. **`load_dotenv()` 的查找路径**：`config.py` 中调用 `load_dotenv()` 时未指定路径，python-dotenv 默认从**当前工作目录**向上查找 `.env`。在根目录运行时能找到 `.env`；在其他目录运行则加载失败，配置回退到默认值。
2. **相对导入**：`src` 内代码使用相对导入（如 `from .config import ...`），只有把项目根目录当作包上下文时（`python -m src.main`）才能正确解析；直接 `python src/main.py` 会报 `ImportError: attempted relative import with no known parent package`。
3. **结论**：必须在项目根目录执行 `python -m src.main`，而不是 `python src/main.py`。

---

## 附：工业级设计要点（面试可讲）

| 设计点 | 本 Demo 的体现 | 面试展开方向 |
| --- | --- | --- |
| 配置外置 | `.env` / `config.py` 集中读取 | 12-Factor 原则、敏感信息不进代码库 |
| 工具即插件 | `registry.py` 注册表 + 执行器映射 | 新增工具零侵入，只加一行注册 |
| 错误兜底 | 未注册工具返回错误文本 | 错误回写给模型，模型可自行纠错重试 |
| 防死循环 | `MAX_ITERATIONS` 迭代上限 | 真实系统还需超时、预算控制 |
| 协议兼容 | 只改 `base_url` 即换云端 | OpenAI 生态通用，可接 OpenAI/通义/DeepSeek 等 |
| 四角色模型 | 用户 / 大模型 / 工具 / 平台（Agent） | 消息流转：user → assistant(tool_calls) → tool → assistant(答案 |
