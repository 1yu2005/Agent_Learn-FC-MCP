"""工具注册表：统一维护工具Schema与执行路由

新增工具分三步：
1.在tools包下新建模块，实现业务函数；
2.在TOOL_SCHEMAS 中补充工具说明书 （OpenAI Function Calling格式）；
3.在 _EXECUTORS 等级 name——>函数。
主循环（agent.py) 无需改动

================================================
在这个文件中：
1.注册了工具说明书列表（包含工具名、描述、参数说明等）
2.注册了工具执行器（将工具名映射到实际函数）
3.定义了执行工具的函数（结合工具执行器使用，根据工具名和参数调用实际函数）
"""
import json
from typing import Any,Callable

from .weather import get_weather   # 从weather模块导入get_weather函数

TOOL_SCHEMAS:list[dict] = [          # 工具说明书列表  ⭐⭐⭐⭐⭐
    {
        "type":"function",                      # 标识为函数调用
        "function":{                            # 函数说明的外壳
            "name":"get_weather",                # 函数名   
            "description":"查询指定城市的实时天气",  # 函数描述
            "parameters":{                        # 函数参数说明
                "type":"object",                    # 参数整体结构，此处为对象
                "properties":{                      # 每一个参数的具体定义
                    "city":{"type":"string","description":"城市名，如 北京"}
                },
                "required":["city"]                # 必填参数列表
                },
            },
    }
]

# 工具执行器注册表：工具名 -> 实际函数
# 新增工具只需在此注册，即"插件模式"
_EXECUTORS:dict[str,Callable[...,Any]] ={     # ⭐⭐⭐⭐⭐   Callable 表示可调用对象，... 表示参数数量可变，Any 表示返回值类型为任意类型
    "get_weather":get_weather,
   }


def execute_tool(name:str,arguments_json:str) -> str:   # ⭐⭐⭐⭐⭐
    """执行工具。

    参数:
        name: 工具名
        arguments_json: 模型生成的参数字符串（JSON 格式）

    返回:
        工具执行结果字符串
    """    # 这个是函数的文档字符串，用于描述函数的功能和参数。
   
    func = _EXECUTORS.get(name)    # 从工具执行器注册表中获取实际可调用的函数/工具
    if func is None:
        return f"工具 {name} 不存在"
    try:
        args = json.loads(arguments_json)   # 因为传进来的参数是JSON字符串（来自大语言模型 的调用），所以需要反序列化为字典
        return func(**args)             # 调用真实函数，返回执行结果  **args 表示将字典中的键值对作为关键字参数传递给函数 func
    except Exception as e:    # 工作异常兜底：写回模型友好处理
        return f"工具 {name} 执行失败：{str(e)}"
    
# 关键字参数：**args 表示将字典中的键值对作为关键字参数传递给函数 func
# 例如：{"city":"北京"} 会转换为 get_weather(city="北京")