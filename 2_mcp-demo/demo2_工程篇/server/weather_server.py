""" 天气/计算/时间 本地工具 MCP Server(FastMCP工程实践)。

FastMCP 是一个基于 FastAPI 的 MCP Server,用于提供本地工具能力。
FastMCP 能 ⭐⭐自动完成⭐⭐ demo1_原理篇中server.py手写的三件事情:
- 协议分发(initialize、tools/list、tools/call)
- 工具Schema生成（从函数签名和docstring自动生成）        docstring是函数的文档字符串，用于描述函数的功能、参数、返回值等信息
- stdio 传输主循环（stdin 读请求、stdout写响应）

我们只需要用 @mcp.tool 装饰器标记工具函数，FastMCP 就能自动生成工具Schema。⭐⭐⭐⭐⭐
"""
import logging      # 导入日志模块,用于记录程序运行时的事件和错误信息
from datetime import datetime

from mcp.server.fastmcp import FastMCP  # 导入 FastMCP 类，用于创建 MCP Server 实例

logger = logging.getLogger("mcp.server.weather")  # 创建日志记录器，用于记录天气工具的运行日志 参数表示日志记录器的名称

# 数据源层：真实项目里替换成天气 API 调用
_WEATHER_DB = {
    "北京": "晴，气温 25°C，空气质量 良",
    "上海": "多云，气温 27°C，空气质量 优",
    "广州": "阵雨，气温 30°C，空气质量 良",
    "深圳": "雷阵雨，气温 29°C，空气质量 良",
    "杭州": "阴，气温 26°C，空气质量 优",
}
_AQI_DB = {"北京": 75, "上海": 40, "广州": 60, "深圳": 55, "杭州": 48}

mcp = FastMCP("weather-server")   # ⭐⭐⭐ 创建 MCP Server 实例（名字会出现在 initialize 的 serverInfo），参数表示服务器名称

@mcp.tool()      # ⭐⭐⭐ 标记为工具函数，用于生成工具Schema  这是语法糖
def get_wearther(city: str) -> str:
    """查询指定城市的当天天气。当用户询问某城市天气、气温时调用本工具。"""
    try:
        return _WEATHER_DB.get(city,f"暂无{city}的天气信息")
    except Exception as e:
        logger.exception("get_weather 执行异常")   # 记录异常日志，包含异常信息  
        return f"查询{city}天气时出错：{e}"

@mcp.tool()
def get_air_quality(city:str) -> str:
     """查询指定城市的空气质量指数（AQI）。当用户询问空气、污染、雾霾时调用本工具。"""
     try:
        api = _AQI_DB.get(city)   # 当城市不在数据库中时，返回 None
        if api is None:
            return f"暂无{city}的空气质量指数"
        level = "优" if aqi <= 50 else "良" if aqi <= 100 else "轻度污染" 
        return f"{city}的空气质量指数为{aqi}，等级为{level}"
     except Exception as e:
        logger.exception("get_air_quality 执行异常")   # 记录异常日志，包含异常信息  
        return f"查询{city}空气质量指数时出错：{e}"

@mcp.tool()
def calculate(expression: str) -> str:
    """计算数学表达式，支持 + - * / 与括号。当用户要求计算时调用本工具。"""
    allowed = set("0123456789-*/()")    # set() 函数将字符串转换为集合，集合中的元素是唯一的，不能重复
    if not set(expression) <= allowed:
        return "参数错误：表达式包含无效字符"
    try:
        result = eval(expression)   # 仅演示：已做白名单过滤；生产请用 ast 或专用解析器  eval() 函数将字符串转换为 Python 表达式并求值
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算表达式时出错：{e}"

@mcp.tool()
def get_current_time() -> str:
    """获取当前时间。当用户询问时间时调用本工具。"""
    return f"当前时间为 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
if __name__ == "__main__":
    mcp.run(transport="stdio")   # 与原理篇的 stdin/stdout 主循环是同一件事
