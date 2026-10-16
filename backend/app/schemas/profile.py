"""
学习画像数据模型
迁移自: 旧项目 schemas/portrait.py 的5维画像设计
适配: 从行为域5维度 → 认知域6维度
核心原则不变: 画像必须是结构化数值，不能只是文字标签
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ================================================================
# 单维度模型 —— 复用旧项目"一维度一指标"的设计思想
# ================================================================
class LearningDimension(BaseModel):
    """单个画像维度，必须同时有 name + score + level + evidence"""
    name: str                           # 维度名
    score: float = Field(ge=0, le=1)   # 0-1标准化得分
    level: str                          # 等级标签: 初级/中级/高级
    evidence: List[str] = []            # 支撑证据（来自对话中的关键信息）
    trend: Optional[float] = None       # 变化趋势: >0上升, <0下降
    updated_at: datetime = Field(default_factory=datetime.now)


# ================================================================
# A3 核心6维画像 —— 对应赛题要求"不少于6个维度"
# ================================================================
class StudentProfile(BaseModel):
    """
    动态学生画像

    迁移说明:
    旧项目5维（学习投入/执行自律/作息规律/资源利用/身体发展）
    → 新项目6维（知识基础/认知风格/易错点偏好/学习节奏/兴趣方向/能力短板）

    设计原则迁移:
    1. 每个维度都要有数值（不只是标签）
    2. 支持增量更新（对话即更新）
    3. 保留历史轨迹（支持演化分析）
    """
    student_id: str
    student_name: Optional[str] = None

    # ---- 6大核心维度 ----
    knowledge_foundation: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="知识基础", score=0.5, level="待评估",
            evidence=["首次对话尚未评估"]
        )
    )
    cognitive_style: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="认知风格", score=0.5, level="待评估",
            evidence=["尚未识别认知偏好"]
        )
    )
    error_preference: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="易错点偏好", score=0.5, level="待评估",
            evidence=["尚未识别易错模式"]
        )
    )
    learning_pace: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="学习节奏", score=0.5, level="中等",
            evidence=["默认中等节奏"]
        )
    )
    interest_direction: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="兴趣方向", score=0.5, level="待探索",
            evidence=["尚未明确兴趣方向"]
        )
    )
    ability_gap: LearningDimension = Field(
        default_factory=lambda: LearningDimension(
            name="能力短板", score=0.5, level="待评估",
            evidence=["尚未进行能力评估"]
        )
    )

    # ---- 学习目标与历史 ----
    learning_goals: List[str] = []          # 用户声明的学习目标
    knowledge_graph: Dict[str, float] = {}   # 知识点 → 掌握度
    conversation_history: List[dict] = []    # 对话摘要（用于增量更新）
    profile_version: int = 1                 # 画像版本号（随更新递增）

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # ============================================================
    # 画像更新方法 —— 复用旧项目"滑动窗口 + 增量更新"策略
    # ============================================================
    def update_dimension(
        self, dim_name: str, new_score: float,
        new_level: str, new_evidence: List[str]
    ):
        """增量更新单个维度 —— 即时窗口滑动"""
        dim = getattr(self, dim_name)
        # 记录趋势（新旧对比）
        dim.trend = new_score - dim.score
        # 更新数值
        dim.score = new_score
        dim.level = new_level
        dim.evidence = (new_evidence + dim.evidence)[:10]  # 保留最近10条
        dim.updated_at = datetime.now()
        self.updated_at = datetime.now()
        self.profile_version += 1

    def get_dimensions_as_dict(self) -> dict:
        """获取所有维度的结构化数据 —— 用于前端雷达图"""
        return {
            dim.name: {
                "score": dim.score,
                "level": dim.level,
                "trend": dim.trend
            }
            for dim in [
                self.knowledge_foundation,
                self.cognitive_style,
                self.error_preference,
                self.learning_pace,
                self.interest_direction,
                self.ability_gap,
            ]
        }

    def get_top_gaps(self, n: int = 3) -> List[dict]:
        """获取最大的能力短板 —— 用于资源推荐优先级"""
        dims = self.get_dimensions_as_dict()
        gaps = sorted(dims.items(), key=lambda x: x[1]["score"])[:n]
        return [{"name": k, **v} for k, v in gaps]
