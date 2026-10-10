"""配置加载：从 .env 读取 Ollama 地址 / 模型名 / 最大迭代轮次。"""
import os

from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录 .env

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen-8B-finetune-int4:latest")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))
