"""
Mistake Insights Service — LLM 驱动的错题智能分析

功能：
  1. 汇总学生全部错题，生成结构化学习行为总结
  2. 识别薄弱知识点和主要错因模式
  3. 推荐类似练习题和学习资料
  4. 对学习状态进行综合评估（强项/弱项/建议）

设计：
  - LLM 可用时：构造结构化 prompt 调用大模型
  - LLM 不可用时：基于规则引擎生成高质量的 fallback 分析
  - 输出格式统一为 JSON，前端可直接渲染
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── LLM Prompt 模板 ──────────────────────────────────────

_SYSTEM_PROMPT = """你是一位资深的学习诊断专家。请根据学生的错题记录，输出一份结构化的学习分析报告。

要求：
1. 总结学生近期的学习行为特征
2. 识别薄弱知识点和主要错因模式
3. 推荐 3 道类似练习题（含答案和解析）
4. 推荐 3 个互补学习资料：至少覆盖一项可视化资源（视频/导图）、一项分步讲解或练习、一个代码或实践任务
5. 对学习状态进行综合评估

输出必须是合法 JSON，格式如下：
{
  "summary": "一句话总结学生近期学习行为",
  "weak_points": [
    {"kp_id": "知识点ID", "reason": "为什么薄弱", "error_count": 数字}
  ],
  "error_pattern": "最主要的错因模式描述",
  "recommendations": {
    "similar_questions": [
      {"question": "题目", "answer": "答案", "explanation": "解析", "bloom_level": "understand"}
    ],
    "learning_materials": [
      {"title": "资料名称", "type": "video/doc/project", "url": "链接或描述", "reason": "推荐理由"}
    ]
  },
  "evaluation": {
    "overall_score": 0.0-1.0,
    "strengths": ["强项1", "强项2"],
    "weaknesses": ["弱项1", "弱项2"],
    "suggestions": ["建议1", "建议2", "建议3"]
  }
}

只输出 JSON，不要任何额外文字。"""


def _build_user_prompt(mistakes: List[Dict[str, Any]], user_id: str) -> str:
    """构造发送给 LLM 的用户消息。"""
    lines = [f"学生ID: {user_id}", f"错题总数: {len(mistakes)}", "", "错题列表:"]

    for i, m in enumerate(mistakes[:30]):  # 最多 30 条避免 token 过长
        q = (m.get("question") or "")[:120]
        sa = (m.get("student_answer") or "")[:80]
        ca = (m.get("correct_answer") or "")[:80]
        et = m.get("error_type") or "未知"
        kp = m.get("kp_id") or "综合"
        resolved = "已解决" if m.get("resolved") else "待复习"
        lines.append(
            f"{i+1}. [{kp}] {et} | {resolved}\n"
            f"   题目: {q}\n"
            f"   学生答案: {sa}\n"
            f"   正确答案: {ca}"
        )

    # 统计信息
    kp_counter: Counter = Counter()
    error_counter: Counter = Counter()
    for m in mistakes:
        kp_counter[m.get("kp_id") or "综合"] += 1
        error_counter[m.get("error_type") or "未知"] += 1

    lines.append("")
    lines.append("知识点错题分布:")
    for kp, cnt in kp_counter.most_common(10):
        lines.append(f"  {kp}: {cnt}道")

    lines.append("")
    lines.append("错因分布:")
    for et, cnt in error_counter.most_common(8):
        lines.append(f"  {et}: {cnt}道")

    return "\n".join(lines)


# ── 规则 Fallback 分析 ────────────────────────────────────

def _rule_based_insights(mistakes: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
    """无 LLM 时基于规则的智能分析。"""

    if not mistakes:
        return {
            "summary": "暂无错题记录，建议通过群聊做题或手动记录错题来启动分析。",
            "weak_points": [],
            "error_pattern": "无数据",
            "recommendations": {
                "similar_questions": [],
                "learning_materials": [],
            },
            "evaluation": {
                "overall_score": 0.0,
                "strengths": [],
                "weaknesses": ["暂无错题数据"],
                "suggestions": ["开始做题以生成学习分析"],
            },
            "source": "rule",
            "generated_at": time.time(),
        }

    # 统计
    kp_counter: Counter = Counter()
    error_counter: Counter = Counter()
    resolved_count = 0
    for m in mistakes:
        kp_counter[m.get("kp_id") or "综合"] += 1
        error_counter[m.get("error_type") or "未知"] += 1
        if m.get("resolved"):
            resolved_count += 1

    total = len(mistakes)
    resolve_rate = resolved_count / total if total > 0 else 0

    # 薄弱知识点
    weak_points = []
    for kp, cnt in kp_counter.most_common(5):
        weak_points.append({
            "kp_id": kp,
            "reason": f"累计 {cnt} 道错题，占错题总量的 {cnt/total*100:.0f}%",
            "error_count": cnt,
        })

    # 主要错因
    top_error = error_counter.most_common(1)
    error_pattern = f"以「{top_error[0][0]}」为主（{top_error[0][1]}道，占 {top_error[0][1]/total*100:.0f}%）" if top_error else "无"

    # 总结
    summary = (
        f"共记录 {total} 道错题，已解决 {resolved_count} 道（掌握率 {resolve_rate*100:.0f}%），"
        f"主要薄弱领域为 {weak_points[0]['kp_id'] if weak_points else '未知'}，"
        f"核心错因为「{top_error[0][0] if top_error else '未知'}」。"
    )

    # 推荐类似题
    similar_questions = _generate_similar_questions(mistakes, error_counter)

    # 推荐学习资料
    learning_materials = _generate_learning_materials(kp_counter)

    # 评估
    overall_score = max(0.3, min(0.95, 0.5 + resolve_rate * 0.4 - (total > 20) * 0.1))
    strengths = []
    if resolve_rate > 0.5:
        strengths.append(f"错题解决率较高（{resolve_rate*100:.0f}%），说明复习积极")
    if len(kp_counter) > 5:
        strengths.append("错题覆盖多个知识点，学习范围广")
    if resolved_count > 5:
        strengths.append("已有较多错题被攻克，学习有成效")

    weaknesses = []
    if resolve_rate < 0.3:
        weaknesses.append("错题解决率偏低，复习积极性需提升")
    if top_error and top_error[0][1] > total * 0.4:
        weaknesses.append(f"错因集中于「{top_error[0][0]}」，需针对性突破")
    if total > 20:
        weaknesses.append("错题数量较多，需系统化复习")

    suggestions = []
    suggestions.append(f"优先复习「{weak_points[0]['kp_id'] if weak_points else '核心知识点'}」，集中突破薄弱环节")
    suggestions.append(f"针对「{top_error[0][0] if top_error else '概念混淆'}」错因做专项练习")
    suggestions.append("利用变式练习巩固薄弱知识点，每道错题至少做 2 道变式")

    return {
        "summary": summary,
        "weak_points": weak_points,
        "error_pattern": error_pattern,
        "recommendations": {
            "similar_questions": similar_questions,
            "learning_materials": learning_materials,
        },
        "evaluation": {
            "overall_score": round(overall_score, 2),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
        },
        "source": "rule",
        "generated_at": time.time(),
    }


def _generate_similar_questions(mistakes: List[Dict], error_counter: Counter) -> List[Dict]:
    """基于错题模式生成推荐练习题。"""
    questions = []

    # 取错因最多的 3 个知识点
    kp_counter: Counter = Counter()
    for m in mistakes:
        kp_counter[m.get("kp_id") or "综合"] += 1

    kp_templates = {
        "transformer": "Transformer 的多头注意力机制中，如果 d_model=768、num_heads=12，每个头的维度是多少？",
        "rag": "RAG 系统中，检索召回率和精度的区别是什么？如何同时优化两者？",
        "cnn": "解释感受野的概念。两层 3×3 卷积叠加的感受野为什么等于一层 5×5 卷积？",
        "linear_algebra": "证明：如果 λ 是矩阵 A 的特征值，那么 λ² 是 A² 的特征值。",
        "python_basics": "解释 Python 中深拷贝和浅拷贝的区别，并举例说明何时使用哪种。",
        "ml_fundamentals": "推导逻辑回归的交叉熵损失函数对权重 w 的梯度。",
        "neural_networks": "解释梯度消失问题。为什么 ReLU 激活函数能部分缓解这个问题？",
        "optimization": "比较 SGD with momentum 和 Adam 优化器在稀疏梯度场景下的表现差异。",
    }

    for kp, cnt in kp_counter.most_common(3):
        kp_base = kp.split("/")[0] if "/" in kp else kp
        template = kp_templates.get(kp_base, f"针对知识点「{kp}」设计一道综合应用题，要求展示完整推理过程。")
        questions.append({
            "question": template,
            "answer": "请参考教材或课件中的标准解答，注意推理过程完整性。",
            "explanation": f"此题针对你错题最多的知识点「{kp}」设计，建议先独立完成再核对答案。",
            "bloom_level": "apply",
            "source_kp": kp,
        })

    return questions[:3]


def _generate_learning_materials(kp_counter: Counter) -> List[Dict]:
    """基于薄弱知识点推荐学习资料。"""
    materials = []
    material_map = {
        "transformer": [
            {"title": "Transformer 结构与张量形状导图", "type": "mindmap", "url": "围绕 Q/K/V、Mask、多头注意力和残差连接建立视觉表征", "reason": "先把抽象结构转成可追踪的图形关系"},
            {"title": "Transformer 可视化教程", "type": "video", "url": "https://jalammar.github.io/illustrated-transformer/", "reason": "用动态流程理解注意力权重与信息流向"},
            {"title": "Self-Attention 维度 Debug 实操", "type": "code", "url": "运行并标注 Q、K、V 与多头拼接的张量形状", "reason": "把公式、维度与可运行代码逐行对齐"},
        ],
        "rag": [
            {"title": "RAG 检索链路可视化导图", "type": "mindmap", "url": "串联分块、嵌入、召回、重排与生成环节", "reason": "先建立完整的检索链路表征"},
            {"title": "RAG 从原理到实践", "type": "doc", "url": "https://python.langchain.com/docs/use_cases/question_answering/", "reason": "分步理解知识库构建与检索接口"},
            {"title": "检索与重排对比实操", "type": "code", "url": "构建一个带召回、重排和证据引用的小型 RAG 问答链路", "reason": "通过可运行案例区分召回与重排的职责"},
        ],
        "cnn": [
            {"title": "CS231n 卷积神经网络", "type": "video", "url": "https://cs231n.github.io/convolutional-networks/", "reason": "斯坦福经典 CNN 课程"},
        ],
        "linear_algebra": [
            {"title": "3Blue1Brown 线性代数本质", "type": "video", "url": "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVUpgQGroULLA", "reason": "直觉理解特征值和矩阵分解"},
        ],
        "python_basics": [
            {"title": "Python 官方教程 - 类与装饰器", "type": "doc", "url": "https://docs.python.org/3/tutorial/classes.html", "reason": "深入理解 Python 面向对象特性"},
        ],
        "ml_fundamentals": [
            {"title": "机器学习 - 周志华", "type": "doc", "url": "教材第3-5章", "reason": "系统掌握偏差方差、正则化等核心概念"},
            {"title": "过拟合与正则化可视化", "type": "video", "url": "https://scikit-learn.org/stable/auto_examples/model_selection/plot_underfitting_overfitting.html", "reason": "直观理解模型复杂度与泛化的关系"},
        ],
        "neural_networks": [
            {"title": "反向传播推导详解", "type": "doc", "url": "https://cs231n.github.io/optimization-2/", "reason": "手推梯度加深理解"},
            {"title": "深度学习中的激活函数", "type": "video", "url": "https://pytorch.org/docs/stable/nn.html#activation-functions", "reason": "对比各激活函数的优缺点"},
        ],
        "optimization": [
            {"title": "优化器对比实验", "type": "project", "url": "用 PyTorch 对比 SGD/Adam/AdamW 在 CIFAR-10 上的表现", "reason": "动手理解不同优化器的特性"},
        ],
    }

    for kp, _ in kp_counter.most_common(5):
        kp_base = kp.split("/")[0] if "/" in kp else kp
        if kp_base in material_map:
            for mat in material_map[kp_base]:
                if len(materials) < 3:
                    materials.append(mat)

    # 补齐到 3 个
    if len(materials) < 3:
        materials.append({
            "title": "错题复盘方法论",
            "type": "doc",
            "url": "建议每周整理一次错题本，按知识点分类归纳解题套路",
            "reason": "系统化的错题复盘是提升学习效率的关键",
        })

    return materials[:3]


# ── 主入口 ───────────────────────────────────────────────

def generate_mistake_insights(
    mistakes: List[Dict[str, Any]],
    user_id: str,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """生成错题智能分析报告。

    Args:
        mistakes: 学生全部错题记录
        user_id: 学生 ID
        use_llm: 是否尝试调用 LLM

    Returns:
        结构化分析报告 dict
    """
    if not mistakes:
        return _rule_based_insights(mistakes, user_id)

    # 尝试 LLM
    if use_llm:
        try:
            from backend.app.core.llm_client import LLMClient

            client = LLMClient()
            user_prompt = _build_user_prompt(mistakes, user_id)

            response = client.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            # 解析 LLM 返回的 JSON
            result = _parse_llm_response(response)
            if result:
                result["source"] = "llm"
                result["generated_at"] = time.time()
                result["user_id"] = user_id
                result["total_mistakes"] = len(mistakes)
                logger.info("[mistake_insights] LLM analysis generated for %s", user_id)
                return result
        except Exception as exc:
            logger.warning("[mistake_insights] LLM failed, fallback to rule: %s", exc)

    # Fallback
    result = _rule_based_insights(mistakes, user_id)
    result["user_id"] = user_id
    result["total_mistakes"] = len(mistakes)
    return result


def _parse_llm_response(text: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 返回的 JSON，兼容 markdown 代码块包裹。"""
    if not text or not text.strip():
        return None

    # 去除 markdown 代码块
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 去掉首尾 ``` 行
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    # 尝试直接解析
    try:
        result = json.loads(cleaned)
        return result if _is_valid_insight_payload(result) else None
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 片段
    import re
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            result = json.loads(match.group())
            return result if _is_valid_insight_payload(result) else None
        except json.JSONDecodeError:
            pass

    return None


def _is_valid_insight_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    recommendations = payload.get("recommendations")
    evaluation = payload.get("evaluation")
    required_lists = (
        payload.get("weak_points"),
        recommendations.get("similar_questions") if isinstance(recommendations, dict) else None,
        recommendations.get("learning_materials") if isinstance(recommendations, dict) else None,
        evaluation.get("strengths") if isinstance(evaluation, dict) else None,
        evaluation.get("weaknesses") if isinstance(evaluation, dict) else None,
        evaluation.get("suggestions") if isinstance(evaluation, dict) else None,
    )
    score = evaluation.get("overall_score") if isinstance(evaluation, dict) else None

    return (
        isinstance(payload.get("summary"), str)
        and isinstance(payload.get("error_pattern"), str)
        and all(isinstance(value, list) for value in required_lists)
        and isinstance(score, (int, float))
        and 0 <= score <= 1
    )
