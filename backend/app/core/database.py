"""
数据库连接管理
SQLite 为主（比赛 Demo），支持后续迁移到 PostgreSQL
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.app.core.config import get_config


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


_config = get_config()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(_project_root() / 'data' / 'a3_learning.db').as_posix()}",
)

# 自动创建数据目录
if DATABASE_URL.startswith("sqlite:///"):
    db_file = DATABASE_URL.replace("sqlite:///", "")
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

def _make_engine(database_url: str):
    return create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=_config.debug,
    )


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def configure_database(database_url: str) -> None:
    """Rebind the global engine/session factory, primarily for tests and CLI tools."""
    global DATABASE_URL, engine
    DATABASE_URL = database_url
    engine = _make_engine(database_url)
    SessionLocal.configure(bind=engine)


def get_db():
    """FastAPI 依赖注入: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表（按需）"""
    from backend.app.core import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
