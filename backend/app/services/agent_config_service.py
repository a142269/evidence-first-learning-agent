"""配置型 Agent 服务 — 教师可通过配置（而非上传代码）新增/编辑 Agent。

设计:
- 内置 6 个 Agent（智狐/智灵/阿匠/小龙/团团/球球）作为 builtin 记录种子化，
  只允许编辑展示信息（name/title/avatar/role_desc）与启用状态，
  不允许改 system_prompt，也不可删除 —— 核心逻辑仍由原 Python Agent 类执行。
- 教师新增的 Agent 为配置驱动（builtin=0），由统一 ConfigurableAgent 执行，
  按 system_prompt + capabilities 调用通用 LLM 回复。
- Orchestrator 在编排前先做 @Agent名称 识别：命中启用的配置型 Agent 走
  ConfigurableAgent；命中已禁用 Agent 返回系统提示。
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.app.core.database import SessionLocal
from backend.app.core.models import AgentConfigRecord

logger = logging.getLogger(__name__)

# 内置 Agent 种子（与前端 constants/companion.ts partners 保持一致）
BUILTIN_AGENT_SEEDS: List[Dict[str, Any]] = [
    {"key": "planner", "name": "智狐", "title": "学习规划师", "role_desc": "任务规划 · 路径编排", "avatar": "/avatars/zhihu.png"},
    {"key": "tutor", "name": "智灵", "title": "知识讲师", "role_desc": "知识讲解 · 答疑引导", "avatar": "/avatars/zhiling.png"},
    {"key": "content", "name": "阿匠", "title": "内容工匠", "role_desc": "资料生成 · 资源制作", "avatar": "/avatars/ajiang.png"},
    {"key": "quiz", "name": "小龙", "title": "小龙挑战", "role_desc": "题库生成 · 难度分层", "avatar": "/avatars/xiaolong.png"},
    {"key": "evaluation", "name": "团团", "title": "熊猫评分", "role_desc": "学习评估 · 效果反馈", "avatar": "/avatars/tuantuan.png"},
    {"key": "safety", "name": "球球", "title": "刺猬守护", "role_desc": "安全审核 · 防幻觉校验", "avatar": "/avatars/qiuqiu.png"},
]

# 教师可编辑字段
_BUILTIN_EDITABLE = {"name", "title", "avatar", "role_desc", "enabled"}
_CUSTOM_EDITABLE = _BUILTIN_EDITABLE | {
    "system_prompt", "capabilities", "allowed_tools",
}


def _row_to_dict(row: AgentConfigRecord) -> Dict[str, Any]:
    return {
        "key": row.key,
        "name": row.name,
        "title": row.title,
        "avatar": row.avatar,
        "role_desc": row.role_desc,
        "system_prompt": row.system_prompt,
        "capabilities": list(row.capabilities or []),
        "allowed_tools": list(row.allowed_tools or []),
        "enabled": bool(row.enabled),
        "builtin": bool(row.builtin),
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class AgentConfigService:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory
        self._seeded = False

    # ---------------- 种子化 ----------------
    def ensure_seeded(self) -> None:
        if self._seeded:
            return
        try:
            with self.session_factory() as db:
                for seed in BUILTIN_AGENT_SEEDS:
                    if db.get(AgentConfigRecord, seed["key"]) is None:
                        db.add(AgentConfigRecord(
                            key=seed["key"],
                            name=seed["name"],
                            title=seed["title"],
                            avatar=seed.get("avatar", ""),
                            role_desc=seed.get("role_desc", ""),
                            system_prompt="",
                            capabilities=[],
                            allowed_tools=[],
                            enabled=1,
                            builtin=1,
                            created_by="system",
                        ))
                db.commit()
            self._seeded = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[agent-config] seed failed: %s", exc)

    # ---------------- 查询 ----------------
    def list(self, include_disabled: bool = True) -> List[Dict[str, Any]]:
        self.ensure_seeded()
        with self.session_factory() as db:
            query = db.query(AgentConfigRecord)
            if not include_disabled:
                query = query.filter(AgentConfigRecord.enabled == 1)
            rows = query.order_by(
                AgentConfigRecord.builtin.desc(),
                AgentConfigRecord.created_at.asc(),
            ).all()
            return [_row_to_dict(r) for r in rows]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        self.ensure_seeded()
        with self.session_factory() as db:
            row = db.get(AgentConfigRecord, key)
            return _row_to_dict(row) if row else None

    # ---------------- 变更 ----------------
    def create(self, data: Dict[str, Any], created_by: str = "") -> Dict[str, Any]:
        self.ensure_seeded()
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("name_required")
        key = str(data.get("key", "")).strip() or f"cfg_{uuid.uuid4().hex[:8]}"
        with self.session_factory() as db:
            if db.get(AgentConfigRecord, key) is not None:
                raise ValueError("agent_key_exists")
            existing_names = {
                r.name for r in db.query(AgentConfigRecord.name).all()
            }
            if name in existing_names:
                raise ValueError("agent_name_exists")
            row = AgentConfigRecord(
                key=key,
                name=name,
                title=str(data.get("title", "")),
                avatar=str(data.get("avatar", "")),
                role_desc=str(data.get("role_desc", "")),
                system_prompt=str(data.get("system_prompt", "")),
                capabilities=list(data.get("capabilities") or []),
                allowed_tools=list(data.get("allowed_tools") or []),
                enabled=1 if data.get("enabled", True) else 0,
                builtin=0,
                created_by=created_by,
                created_at=time.time(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _row_to_dict(row)

    def update(self, key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_seeded()
        with self.session_factory() as db:
            row = db.get(AgentConfigRecord, key)
            if row is None:
                raise KeyError("agent_not_found")
            editable = _BUILTIN_EDITABLE if row.builtin else _CUSTOM_EDITABLE
            for field, value in updates.items():
                if field not in editable:
                    continue
                if field == "enabled":
                    row.enabled = 1 if value else 0
                elif field in ("capabilities", "allowed_tools"):
                    setattr(row, field, list(value or []))
                else:
                    setattr(row, field, str(value))
            row.updated_at = time.time()
            db.commit()
            db.refresh(row)
            return _row_to_dict(row)

    def delete(self, key: str) -> bool:
        self.ensure_seeded()
        with self.session_factory() as db:
            row = db.get(AgentConfigRecord, key)
            if row is None:
                return False
            if row.builtin:
                raise ValueError("builtin_agent_not_deletable")
            db.delete(row)
            db.commit()
            return True

    # ---------------- @ 识别 ----------------
    def find_mentioned(self, text: str) -> Optional[Dict[str, Any]]:
        """在用户输入中识别 @配置型Agent（仅教师新增的，内置 Agent 由 orchestrator 原逻辑处理）。

        返回命中的配置 dict（含 enabled 状态，由调用方决定禁用时的行为）。
        """
        if "@" not in text:
            return None
        try:
            configs = self.list(include_disabled=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[agent-config] find_mentioned failed: %s", exc)
            return None
        # 名称长的优先匹配，避免 "论文助教Pro" 被 "论文助教" 抢先命中
        custom = sorted(
            (c for c in configs if not c["builtin"] and c["name"]),
            key=lambda c: len(c["name"]),
            reverse=True,
        )
        for config in custom:
            if f"@{config['name']}" in text:
                return config
        return None


_service: AgentConfigService | None = None


def get_agent_config_service() -> AgentConfigService:
    global _service
    if _service is None:
        _service = AgentConfigService()
    return _service


def strip_mention(text: str, name: str) -> str:
    """去掉 @名称 前缀，保留问题正文。"""
    return re.sub(rf"@{re.escape(name)}[\s,，:：]*", "", text).strip()
