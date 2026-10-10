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
import os  # 用于获取环境变量
import random

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.server.xxapi")      # 定义日志记录器，用于记录日志

load_dotenv()    # Server进程在项目根目录启动，可读取 .env 文件中的环境变量
XXAPI_BASE = os.getenv("XXAPI_BASE", "https://v2.xxapi.cn").strip("/")   #strip() 方法用于移除字符串头尾指定的字符（默认为空格）或字符序列
# 官方文档建议携带该UA，避免被限流
HEADERS = {"User-Agent": "xiaoxiaoapi/1.0.0 (https://xxapi.cn)"}   # 定义请求头，包含 User-Agent 字段

mcp = FastMCP("xxapi-server")  #⭐⭐⭐ 初始化 FastMCP 实例，指定 Server 名称为 "xxapi-server"

def _call(endpoint:str,params:dict) -> str:
    """通用封装：请求小小API接口，把 data 转成模型可读文本(JSON 字符串格式)
      本函数是所有工具的底层，根据 endpoint 和 params 构建请求 URL，发送请求，返回 JSON 字符串。
    """
    try:
        resp = requests.get(
            f"{XXAPI_BASE}/{endpoint}",  # 构建请求 URL，包含 endpoint
            headers=HEADERS,             # 携带 User-Agent 字段，避免被限流
            params=params,               # 传递参数
            timeout=10,                  # 设置请求超时时间为 10 秒
        )
        data = resp.json()               # 解析 JSON 响应体
    except Exception as e:
        logger.exception("API 请求异常")
        return f"API 请求失败：{exc}"
    if data.get("code") != 200:          # 检查状态码是否为 200，即成功
        return f"API 请求失败：{data.get('msg', '未知错误')}"
    return json.dumps(data.get("data", {}), ensure_ascii=False, indent=2)    # 序列化 data 字段，确保中文字符正常显示,indent=2 用于格式化输出，使 JSON更易读

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

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 启动 MCP Server，监听标准输入输出