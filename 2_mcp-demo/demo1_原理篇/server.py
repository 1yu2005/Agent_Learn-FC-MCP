"""【原理篇】
MCP Server：是工具、资源、提示词模板的提供方。与MCP Client 通过 JSON-RPC 2.0 协议一对一通信。
手写 MCP Server：JSON-RPC 2.0 + stdio

MCP 的底层其实非常简单，核心就3件事：
1.两个进程之间用哪种管道通信（即 Transport,定义消息怎么在Host和Server之间传递）。
    1.1 stdio(标准输入输出) ————> 本地：Server 作为 Host 的子进程运行
    1.2 Streamable HTTP ————> 远程：Server 部署在远端服务器 / 云服务。Server 作为 HTTP 服务运行，Host 作为 HTTP 客户端运行
2.消息格式是 ISON-RPC 2.0 （每一条消息就是一行JSON，加newline-delimited JSON）     JSON是一种纯文本表示数据的格式，常常长得像字典或数组
3.协议约定三个方法：
    3.1 initialize:握手。Client 问"你是谁、支持什么能力"，Server 回答。【client 向 server 发送 initialize 方法，server 回复 initialize 方法，确认握手成功】
    3.2 tools/list:查询所有工具。Client 问"你支持哪些工具"，Server 返回工具清单（Schema）。【client 向 server 发送 tools/list 方法，server 回复 tools/list 方法，包含所有工具的列表】
    3.3 tools/call:调用工具。Client 说"请执行某个工具，参数是 xxx"，Server 执行后返回结果。【client 向 server 发送 tools/call 方法，server 回复 tools/call 方法，包含工具执行结果】

本文件不 import 任何 mcp 包，纯标准库实现，
每一行都在还原官方 SDK 内部替你做的事情。
"""

import json # 用于解析 JSON 字符串
import sys # 用于获取标准输入输出
from datetime import datetime  # 用于生成时间戳

# 强制 stdio 以 UTF-8 读写：Windows 下 Python 默认 stdout 编码是 GBK，
# 中文消息会按 GBK 写出，而 Client 按 UTF-8 读取，导致 UnicodeDecodeError
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

# ========================工具定义======================= ⭐⭐
# 这就是“Server 具备提供工具”的能力：工具（即 Function） + 工具说明书列表
# 先定义工具/函数，再定义工具说明书列表(完成注册)

_WEATHER_DB = {         # 模拟天气数据库（真实项目这里换成调用天气的API
    "北京": "晴，气温 25°C",
    "上海": "多云，气温 27°C",
    "广州": "阵雨，气温 30°C",
}

# =======工具=======⭐
def _get_weather(city: str) -> str:
    """根据城市查询天气"""
    return _WEATHER_DB.get(city, "未找到该城市的天气信息")

def _get_current_time() -> str:
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")    # .strftime() 方法格式化时间

# ======= 工具说明书列表=======⭐
TOOL_SCHEMAS = [
    {
        "type":"function",
        "function":{
            "name":"get_weather",
            "description":"根据指定城市查询天气",
            "parameters":{
                "type":"object",
                "properties":{
                    "city":{
                        "type":"string",
                        "description":"要查询的城市的名称,如 北京、上海、广州等"
                    }
                },
                "required":["city"],
            },
        },
    },
    {
        "type":"function",
        "function":{
            "name":"get_current_time",
            "description":"获取当前系统日期与时间",
            "parameters":{"type":"object","properties":{}},   # 无参数
        },
    },
]

# ====工具执行器注册表：工具名 -> 实际函数====⭐
# 新增工具只需在此注册，即"插件模式"
EXECUTORS = {
    "get_weather": _get_weather,
    "get_current_time": _get_current_time,
}

# ========================协议处理======================= ⭐⭐
def handle_request(request:dict) -> dict:
    """
    处理一条 Client 发来的JSON-RPC 请求，返回响应

    这是整个MCP Server 的核心：按method字段分发到不同的逻辑
    """
    method = request.get("method")  # 请求的方法名：initialize、tools/list、tools/call
    params = request.get("params",{})  # 请求的参数：根据不同方法不同，参数也不同
    result = None

    if method == "initialize":
        # 握手：告诉 Client协议版本、支持的能力、我是谁⭐
        result = {
            "protocolVersion": "2024-11-05",      # 协议版本号
            "capabilities": {"tools": {}},        # 我支持 tools 能力
            "serverInfo": {"name": "protocol-server", "version": "1.0.0"},
        }
    elif method == "tools/list":
        # 查询所有工具：返回工具清单（Schema）(Client拿到后可以转给模型使用，模型 Function Calling)⭐
        result = {"tools":TOOL_SCHEMAS}
    elif method == "tools/call":
        # 执行工具：name 是要调用的工具名，arguments是参数dict⭐
        name = params.get("name")
        arguments = params.get("arguments",{})
        func = EXECUTORS.get(name)    # 从注册表中获取工具函数
        if func is None:
            text = f"错误：未注册的工具{name}"
        else:
            try:
                text = func(**arguments)  # 把参数展开为关键字参数传给工具函数 ，返回执行结果
            except Exception as e:
                text = f"错误：执行工具{name}时出错，错误信息：{str(e)}"
        # MCP 规定：工具结果必须包成content文本块列表
        result = {"content":[{"type":"text","text":text}]}
    else:
        result = {"error":f"错误：未知的方法名 {method}"}  # 不是initialize、tools/list、tools/call 三种方法

    # 组装 JSON-RPC 响应：jsonrpc 版本 + 请求的 id（必须回同一个 id）+ 结果  
    # 模型调用工具的指令中有一个字段是：tool_calls.id,通过该字段，当有多个工具调用时，可以对应到正确的工具结果
    return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}  # ⭐⭐⭐⭐⭐

# ========================传输主循环（Transport）========================= ⭐⭐
def main() -> None:
    """一直读 stdin，处理一条请求回一条响应。

    sys.stdin 是标准输入（Client 写的管道那一端），
    sys.stdout 是标准输出（Client 读的管道那一端）。
    """
    # 逐行读取Client 发来的请求（每行一条 JSON）
    for line in sys.stdin:
        if not line.strip():
            continue  # 跳过空行
        try:
            request = json.loads(line)  # 解析 JSON 字符串为 dict
            response = handle_request(request)  # 交给协议分发处理，返回响应 dict
        except Exception as e:
            # JSON 解析失败：按 JSON-RPC 规范回错误码 -32700
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": str(e)}} 
         # 把响应写回 stdout，必须 flush（不 flush Client 那边读不到）
        sys.stdout.write(json.dumps(response,ensure_ascii=False) + "\n")
        sys.stdout.flush()   # flush 确保写入到管道

if __name__ == "__main__":
    main()

