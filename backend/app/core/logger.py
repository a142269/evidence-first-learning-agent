"""
日志配置 —— 结构化日志 + 文件/控制台双输出
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from backend.app.core.config import get_config

config = get_config()

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """初始化全局日志配置"""
    level = logging.DEBUG if config.debug else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有的 handler
    root.handlers.clear()

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(console)

    # 文件输出（按大小轮转）
    file_handler = RotatingFileHandler(
        LOG_DIR / "a3_agent.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root.addHandler(file_handler)

    # 降低第三方库日志级别
    for lib in ["uvicorn", "sqlalchemy", "chromadb", "httpx"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger"""
    return logging.getLogger(name)
