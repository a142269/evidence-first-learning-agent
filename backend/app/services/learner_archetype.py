"""
学习者画像类型服务（Learner Archetype）

**移植自老项目** `student-behavior-analysis/backend/app/services/reports/report_enrichment.py`
中的 `ARCHETYPES` 体系。

老项目用 5 维行为分数（学习行为/学习成果/生活节律/社交/选课探索）做画像类型判别，
A3 在此基础上：
1. 维度替换为 A3 的 8 维长期画像（knowledge_base / learning_preference / weak_points /
   time_management / self_efficacy / cognitive_style / learning_goal / interaction_pattern）
2. 8 种类型保留老项目的"昵称式 archetype 描述法"（评委印象深刻）
3. 新增 1 种 A3 专属类型 "概念探索者"，对应 self_efficacy 中等但 cognitive_style 偏抽象推理的群体
4. 输出 traits 直接成为 EvaluatorAgent 的报告素材

学术对齐：
- 借鉴 Felder-Silverman 学习风格模型（视觉/听觉/动手/读写）
- 借鉴 Vermunt 1996 学习方式分类（深度/再现/应用/未定向）

使用：
  from backend.app.services.learner_archetype import LearnerArchetypeService

  svc = LearnerArchetypeService()
  result = svc.identify(profile_dimensions)
  # result = {
  #     "code": "high_achiever",
  #     "archetype": "自驱引领者",
  #     "nickname": "笃行的探路人",
  #     "description": "...",
  #     "traits": [...],
  #     "study_strategy": "...",
  #     "resource_preferences": [...]
  # }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 9 种学习者画像类型（8 种老项目迁移 + 1 种 A3 新增）
# ---------------------------------------------------------------------------
ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "high_achiever": {
        "archetype": "自驱引领者",
        "nickname": "笃行的探路人",
        "description": "知识基础扎实、自我效能高、目标清晰，具备较强的学习自主性。属于可作为同伴标杆的学习者。",
        "study_strategy": "维持稳定节奏 + 引入挑战性任务，避免在舒适区过度停留。",
        "resource_preferences": ["拓展阅读", "实操项目", "进阶习题", "学术论文导读"],
        "bloom_target": ["analyze", "evaluate", "create"],  # 引导至高阶认知
    },
    "effort_chaser": {
        "archetype": "努力追赶者",
        "nickname": "勤恳的赶路人",
        "description": "学习投入稳定、态度端正，但知识掌握尚未与投入匹配。多见于学习方法/题型训练方向需调整的学习者。",
        "study_strategy": "调整学习方法 + 强化错题归因 + 间隔重复，让投入真正转化为掌握。",
        "resource_preferences": ["错题精讲", "类比讲解", "针对性练习", "思维导图"],
        "bloom_target": ["understand", "apply"],
    },
    "rhythm_broken": {
        "archetype": "节律失控型",
        "nickname": "疲惫的夜行者",
        "description": "时间管理薄弱，作息或学习节奏不稳定，常导致学习行为间歇性中断。优先解决节律问题，再谈学习投入。",
        "study_strategy": "建立最小可持续学习闭环（每日 25 分钟番茄钟起步），再扩大学习半径。",
        "resource_preferences": ["短视频讲解", "微章节文档", "每日打卡题", "5 分钟知识点卡片"],
        "bloom_target": ["remember", "understand"],
    },
    "habit_breakdown": {
        "archetype": "习惯断层型",
        "nickname": "走神的旁观者",
        "description": "日常学习行为发生频率整体偏低，呈现「在场但不在线」状态。需要重建最小可持续的学习闭环。",
        "study_strategy": "从低门槛任务起步（每日 1 道题），用成就感重建习惯。",
        "resource_preferences": ["游戏化练习", "成就解锁卡片", "趣味知识点动画", "极简文档"],
        "bloom_target": ["remember"],
    },
    "introverted_explorer": {
        "archetype": "内敛探索型",
        "nickname": "低调的独行者",
        "description": "交互模式偏被动、学习偏好独立钻研。既无明显风险也未形成同伴支持网络。",
        "study_strategy": "保留独立钻研空间 + 引入异步协作（论坛/代码评审）替代实时交流。",
        "resource_preferences": ["深度文档", "代码案例", "拓展阅读", "异步答疑"],
        "bloom_target": ["analyze", "evaluate"],
    },
    "social_learner": {
        "archetype": "社交协作型",
        "nickname": "校园里的同行者",
        "description": "交互模式活跃，偏好合作学习与讨论。学业投入尚可，但易被社交分散注意力。",
        "study_strategy": "组建学习小组 + 用「教别人」的费曼方法巩固知识。",
        "resource_preferences": ["小组项目", "辩论题", "案例研讨", "结对编程"],
        "bloom_target": ["apply", "analyze"],
    },
    "stable_average": {
        "archetype": "稳态中游型",
        "nickname": "规律的常驻生",
        "description": "8 维大致均衡，无明显风险也无显著亮点。适合选定 1 个优势维度做重点突破打开成长空间。",
        "study_strategy": "选定 1 个最感兴趣方向深耕，避免「样样通样样松」。",
        "resource_preferences": ["专题深度文档", "项目实战", "竞赛题", "前沿动态"],
        "bloom_target": ["apply", "analyze"],
    },
    "exam_oriented": {
        "archetype": "考试导向型",
        "nickname": "目标坚定的应试者",
        "description": "学习目标明确为考试/认证，时间紧凑但缺乏延展。需在「拿分」之外补充对知识结构的理解。",
        "study_strategy": "高频刷题 + 配套知识图谱，避免只会做题不懂原理。",
        "resource_preferences": ["真题精讲", "考点速记卡", "高频题库", "公式手册"],
        "bloom_target": ["remember", "understand", "apply"],
    },
    # A3 专属新增类型
    "concept_explorer": {
        "archetype": "概念探索者",
        "nickname": "追问本质的思考者",
        "description": "认知风格偏抽象推理，对「为什么」的关注高于「怎么做」。常因纠结底层原理而进度偏慢，但理解一旦建立非常牢固。",
        "study_strategy": "先给直觉性类比再给数学推导，避免一上来就堆公式；用思维导图串联跨章节概念。",
        "resource_preferences": ["原理性长文", "论文导读", "类比图解", "概念辨析题"],
        "bloom_target": ["understand", "analyze", "evaluate"],
    },
}


# ---------------------------------------------------------------------------
# 工具函数（移植自老项目并适配 A3 字段名）
# ---------------------------------------------------------------------------
def _to_num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, dict):
        # A3 的 dimension 值结构：{"score": 0.7, "level": "中级", "evidence": [...]}
        value = value.get("score", default)
    try:
        num = float(value)
    except Exception:
        return default
    # 老项目用 0-1，A3 也用 0-1，统一裁剪
    if num < 0:
        return 0.0
    if num > 1.0:
        return num / 100.0 if num <= 100 else 1.0
    return num


# ---------------------------------------------------------------------------
# 主服务
# ---------------------------------------------------------------------------
@dataclass
class LearnerArchetypeService:
    """学习者画像类型识别服务"""

    ARCHETYPES = ARCHETYPES

    def identify(self, profile_dimensions: Dict[str, Any]) -> Dict[str, Any]:
        """
        识别学习者类型。

        Args:
            profile_dimensions: A3 的 8 维 dimensions 字段，结构例如：
                {
                    "knowledge_base":     {"score": 0.7, ...},
                    "learning_preference":{"score": 0.5, ...},
                    "weak_points":        {"score": 0.4, ...},
                    "time_management":    {"score": 0.6, ...},
                    "self_efficacy":      {"score": 0.8, ...},
                    "cognitive_style":    {"score": 0.5, ...},
                    "learning_goal":      {"score": 0.6, ...},
                    "interaction_pattern":{"score": 0.7, ...},
                }

        Returns:
            完整的 archetype 对象（含 code/archetype/nickname/description/traits/strategy 等）
        """
        kb = _to_num(profile_dimensions.get("knowledge_base"))
        lp = _to_num(profile_dimensions.get("learning_preference"))
        wp = _to_num(profile_dimensions.get("weak_points"))    # 注：越高代表薄弱点已识别越多
        tm = _to_num(profile_dimensions.get("time_management"))
        se = _to_num(profile_dimensions.get("self_efficacy"))
        cs = _to_num(profile_dimensions.get("cognitive_style"))
        lg = _to_num(profile_dimensions.get("learning_goal"))
        ip = _to_num(profile_dimensions.get("interaction_pattern"))

        # 判别规则（迁移自老项目五维 + 适配 A3 八维）
        # 优先级：高效自驱 > 节律失控 > 习惯断层 > 内敛 / 社交 > 应试 > 概念探索 > 努力追赶 > 稳态
        code: str
        if kb >= 0.65 and se >= 0.65:
            code = "high_achiever"
        elif tm < 0.4 and kb < 0.55:
            code = "rhythm_broken"
        elif kb < 0.4 and se < 0.4:
            code = "habit_breakdown"
        elif ip < 0.35 and lp >= 0.5:
            code = "introverted_explorer"
        elif ip >= 0.65 and kb < 0.6:
            code = "social_learner"
        elif lg >= 0.7 and tm >= 0.6 and kb < 0.7:
            code = "exam_oriented"
        elif cs >= 0.6 and se >= 0.5 and kb < 0.6:
            code = "concept_explorer"
        elif kb >= 0.5 and se < 0.45:
            code = "effort_chaser"
        else:
            code = "stable_average"

        meta = ARCHETYPES[code]
        traits = self._format_traits(kb, lp, wp, tm, se, cs, lg, ip)

        return {
            "code": code,
            **meta,
            "name": meta["archetype"],
            "traits": traits,
            "scores_snapshot": {
                "knowledge_base": round(kb, 3),
                "learning_preference": round(lp, 3),
                "weak_points": round(wp, 3),
                "time_management": round(tm, 3),
                "self_efficacy": round(se, 3),
                "cognitive_style": round(cs, 3),
                "learning_goal": round(lg, 3),
                "interaction_pattern": round(ip, 3),
            },
        }

    def _format_traits(
        self,
        kb: float, lp: float, wp: float, tm: float,
        se: float, cs: float, lg: float, ip: float,
    ) -> List[str]:
        """每个维度生成一句人话描述"""
        def _level(v: float) -> str:
            return "偏强" if v >= 0.6 else "偏弱" if v < 0.4 else "中位"
        return [
            f"知识基础 {kb:.2f}（{_level(kb)}）",
            f"学习偏好 {lp:.2f}（{_level(lp)}）",
            f"薄弱识别 {wp:.2f}（{_level(wp)}）",
            f"时间管理 {tm:.2f}（{_level(tm)}）",
            f"自我效能 {se:.2f}（{_level(se)}）",
            f"认知风格 {cs:.2f}（{_level(cs)}）",
            f"学习目标 {lg:.2f}（{_level(lg)}）",
            f"交互模式 {ip:.2f}（{_level(ip)}）",
        ]

    def get_all_archetypes(self) -> List[Dict[str, Any]]:
        """前端用：列出全部 9 种类型供 ProfileView 展示"""
        out = []
        for code, meta in ARCHETYPES.items():
            out.append({"code": code, **meta, "name": meta["archetype"]})
        return out


# 全局单例
_service: Optional[LearnerArchetypeService] = None


def get_learner_archetype_service() -> LearnerArchetypeService:
    global _service
    if _service is None:
        _service = LearnerArchetypeService()
    return _service
