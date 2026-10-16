#!/usr/bin/env python3
"""Import curated mistake samples and replace legacy vague demo questions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api.v1.mistakes import seed_mistakes
from backend.app.core.database import SessionLocal
from backend.app.core.models import MistakeRecord


SOURCE = "mistake-content-enrichment-v1"

CONCRETE_REPLACEMENTS: dict[str, dict[str, str]] = {
    "AI_001": {
        "question": "在图灵测试中，如果机器只靠预设话术骗过评审，能否据此断言它真正理解了问题？请说明理由。",
        "student_answer": "能，只要评审分辨不出来，就说明机器已经具有人类水平的理解能力。",
        "correct_answer": "不能。图灵测试衡量的是对话行为是否难以区分，并不能直接证明机器具有语义理解、意识或通用推理能力。",
        "explanation": "应区分外显行为评价与内部认知能力，避免把测试通过等同于真正理解。",
        "error_type": "conceptual_misunderstanding",
    },
    "AI_002": {
        "question": "A* 搜索中，节点 A 的 g=4、h=6，节点 B 的 g=7、h=2。下一步应扩展哪个节点？请写出两个节点的 f 值。",
        "student_answer": "扩展 A，因为 A 的路径代价 g 更小。",
        "correct_answer": "f(A)=4+6=10，f(B)=7+2=9，应优先扩展 f 值更小的节点 B。",
        "explanation": "A* 按 f(n)=g(n)+h(n) 选择节点，不能只比较已经发生的路径代价 g。",
        "error_type": "calculation_error",
    },
    "AI_003": {
        "question": "已知子句 (P∨Q)、(¬P∨R)、(¬Q)，请用归结法推出 R，并写出每一步使用的两个子句。",
        "student_answer": "三个子句之间没有互补文字，无法推出 R。",
        "correct_answer": "先由 (P∨Q) 与 (¬Q) 归结得到 P，再由 P 与 (¬P∨R) 归结得到 R。",
        "explanation": "归结需要逐步寻找互补文字，第一次消去 Q，第二次消去 P。",
        "error_type": "application_transfer",
    },
    "AI_004": {
        "question": "训练房价预测模型时，先用全部数据计算均值和方差，再划分训练集与测试集。这个流程有什么问题，应如何修正？",
        "student_answer": "没有问题，标准化只改变数值范围，不会影响测试结果。",
        "correct_answer": "这会造成测试集信息泄漏。应先划分数据，只用训练集拟合均值和方差，再用同一组参数转换验证集和测试集。",
        "explanation": "任何从测试集计算得到的统计量都会使离线评估偏乐观。",
        "error_type": "careless_error",
    },
    "AI_005": {
        "question": "欺诈交易只占 1%，模型把所有样本都预测为正常时准确率仍为 99%。为什么该指标具有误导性？应补充哪些指标？",
        "student_answer": "99% 的准确率说明模型效果很好，不需要其他指标。",
        "correct_answer": "模型完全漏掉了欺诈样本。应重点查看精确率、召回率、F1、PR-AUC，并结合混淆矩阵评估少数类识别能力。",
        "explanation": "类别极不平衡时，准确率会被多数类主导，必须单独衡量少数类表现。",
        "error_type": "reading_comprehension",
    },
}


def replace_vague_questions(user_id: str) -> int:
    updated = 0
    with SessionLocal() as db:
        rows = db.query(MistakeRecord).filter(MistakeRecord.user_id == user_id).all()
        for row in rows:
            data = dict(row.question_data or {})
            question = str(data.get("question") or data.get("stem") or "")
            replacement = CONCRETE_REPLACEMENTS.get(str(row.knowledge_point_id or ""))
            if not replacement or not question.startswith("关于 AI_"):
                continue
            row.question_data = {
                **data,
                "question": replacement["question"],
                "stem": replacement["question"],
                "student_answer": replacement["student_answer"],
                "correct_answer": replacement["correct_answer"],
                "explanation": replacement["explanation"],
                "source": SOURCE,
                "synthetic_demo": True,
            }
            row.error_type = replacement["error_type"]
            row.analysis = replacement["explanation"]
            updated += 1
        db.commit()
    return updated


def enrich(user_id: str) -> dict[str, Any]:
    imported = seed_mistakes(user_id=user_id)
    rewritten = replace_vague_questions(user_id)
    with SessionLocal() as db:
        total = db.query(MistakeRecord).filter(MistakeRecord.user_id == user_id).count()
        concrete = 0
        for row in db.query(MistakeRecord).filter(MistakeRecord.user_id == user_id).all():
            data = row.question_data or {}
            question = str(data.get("question") or data.get("stem") or "")
            concrete += int(bool(question) and not question.startswith("关于 AI_"))
    return {
        "user_id": user_id,
        "imported": int(imported.get("imported", 0)),
        "skipped": int(imported.get("skipped", 0)),
        "rewritten": rewritten,
        "total": total,
        "concrete_questions": concrete,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="demo-student-1")
    args = parser.parse_args()
    print(json.dumps(enrich(args.user_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
