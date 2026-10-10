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