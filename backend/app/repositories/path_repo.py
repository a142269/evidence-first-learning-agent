from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from backend.app.core.database import SessionLocal
from backend.app.core.models import LearningPathRecord


class LearningPathRepository:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    @staticmethod
    def _serialize(row: LearningPathRecord) -> dict[str, Any]:
        # Older teacher assignments stored their extra fields one level below
        # ``metadata``.  Flatten that legacy shape on read so callers see the
        # same contract as newly-created paths (recommended_role, course, etc.).
        metadata = deepcopy(row.metadata_data or {})
        legacy_metadata = metadata.pop("metadata", {})
        if isinstance(legacy_metadata, dict):
            metadata = {**legacy_metadata, **metadata}
        return {
            "id": row.id,
            "user_id": row.user_id,
            "title": row.title,
            "stages": deepcopy(row.stages or []),
            "current_stage": row.current_stage,
            "progress": row.progress,
            "created_at": row.created_at,
            **metadata,
        }

    def save(self, path: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as db:
            try:
                row = db.get(LearningPathRecord, str(path["id"]))
                if row is None:
                    row = LearningPathRecord(id=str(path["id"]))
                    db.add(row)
                known = {
                    "id", "user_id", "title", "stages", "current_stage",
                    "progress", "created_at", "updated_at",
                }
                row.user_id = str(path.get("user_id", ""))
                row.title = str(path.get("title", "学习路径"))
                row.stages = deepcopy(path.get("stages", []))
                row.current_stage = int(path.get("current_stage", 0))
                row.progress = float(path.get("progress", 0.0))
                if "created_at" in path:
                    row.created_at = float(path["created_at"])
                row.metadata_data = {k: deepcopy(v) for k, v in path.items() if k not in known}
                db.commit()
                db.refresh(row)
                return self._serialize(row)
            except Exception:
                db.rollback()
                raise

    def get(self, path_id: str) -> dict[str, Any] | None:
        with self.session_factory() as db:
            row = db.get(LearningPathRecord, path_id)
            return self._serialize(row) if row else None

    def list(self, user_id: str = "") -> list[dict[str, Any]]:
        with self.session_factory() as db:
            query = db.query(LearningPathRecord)
            if user_id:
                query = query.filter(LearningPathRecord.user_id == user_id)
            rows = query.order_by(LearningPathRecord.created_at.desc()).all()
            return [self._serialize(row) for row in rows]

    def continue_completed_teacher_path(self, path_id: str) -> dict[str, Any] | None:
        """Extend a legacy one-stage teacher recommendation after it is completed.

        A single stage is useful as a targeted intervention, but it must not
        leave the learner at a dead end once marked done.  The continuation is
        deliberately anchored to the teacher's original stage rather than
        inventing an unrelated topic.
        """
        with self.session_factory() as db:
            try:
                row = db.get(LearningPathRecord, path_id)
                if row is None:
                    return None
                metadata = dict(row.metadata_data or {})
                legacy_metadata = metadata.get("metadata", {})
                effective_metadata = {
                    **(legacy_metadata if isinstance(legacy_metadata, dict) else {}),
                    **metadata,
                }
                stages = list(row.stages or [])
                if (
                    effective_metadata.get("recommended_role") != "teacher"
                    or len(stages) != 1
                    or int(row.current_stage or 0) < len(stages)
                ):
                    return self._serialize(row)

                anchor = str(stages[0].get("title") or stages[0].get("name") or "本阶段知识").strip()
                stages.extend([
                    {
                        "id": "teacher-followup-2",
                        "title": f"{anchor}巩固与错因订正",
                        "name": f"{anchor}巩固与错因订正",
                        "topics": [anchor],
                        "description": "通过针对性练习、错因复盘和讲解巩固核心方法。",
                        "assessment": "完成巩固练习并订正错因",
                        "order": 2,
                        "generated_from": "teacher_path_continuation",
                    },
                    {
                        "id": "teacher-followup-3",
                        "title": f"{anchor}综合应用与阶段测验",
                        "name": f"{anchor}综合应用与阶段测验",
                        "topics": [anchor],
                        "description": "把本阶段知识迁移到综合题或小型应用中，形成可验证的学习成果。",
                        "assessment": "完成综合应用与阶段测验",
                        "order": 3,
                        "generated_from": "teacher_path_continuation",
                    },
                ])
                row.stages = stages
                row.progress = round(int(row.current_stage or 0) / len(stages) * 100, 1)
                metadata["auto_continuation_generated"] = True
                row.metadata_data = metadata
                db.commit()
                db.refresh(row)
                return self._serialize(row)
            except Exception:
                db.rollback()
                raise

    def update_progress(
        self, path_id: str, stage_index: int, completed: bool
    ) -> dict[str, Any] | None:
        with self.session_factory() as db:
            try:
                row = db.get(LearningPathRecord, path_id)
                if row is None:
                    return None
                stages = row.stages or []
                if completed and 0 <= stage_index < len(stages):
                    row.current_stage = stage_index + 1
                    row.progress = (stage_index + 1) / max(len(stages), 1) * 100
                    db.commit()
                    db.refresh(row)
                return self._serialize(row)
            except Exception:
                db.rollback()
                raise
