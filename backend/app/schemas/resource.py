"""
资源生成相关数据模型
迁移自: 旧项目 schemas/ 的 Pydantic 设计模式
新增: 多模态资源类型定义
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum


class ResourceType(str, Enum):
    """资源类型 —— A3要求至少5种"""
    DOCUMENT = "document"        # 课程讲解文档
    MINDMAP = "mindmap"          # 知识点思维导图
    EXERCISE = "exercise"        # 练习题
    READING = "reading"          # 拓展阅读材料
    VIDEO = "video"              # 多模态教学视频/动画
    CODE_CASE = "code_case"      # 代码实操案例（加分）


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExerciseType(str, Enum):
    CHOICE = "choice"      # 选择题
    FILL = "fill"          # 填空题
    ESSAY = "essay"        # 简答题
    CODE = "code"          # 编程题
    TRUE_FALSE = "tf"      # 判断题


# ---- 学习资源 ----
class LearningResource(BaseModel):
    """个性化学习资源"""
    resource_id: str
    resource_type: ResourceType
    title: str
    content: str                          # 主要内容（Markdown格式）
    knowledge_points: List[str] = []      # 关联知识点
    difficulty: Difficulty = Difficulty.MEDIUM
    estimated_time_minutes: int = 15      # 预计学习时间
    generated_at: datetime = Field(default_factory=datetime.now)
    based_on_profile_version: int = 1     # 基于哪个版本的画像生成


class Exercise(LearningResource):
    """练习题"""
    resource_type: ResourceType = ResourceType.EXERCISE
    exercise_type: ExerciseType
    question: str
    options: Optional[List[str]] = None   # 选择题选项
    answer: str                           # 答案
    explanation: str = ""                 # 解析


class MindMap(LearningResource):
    """思维导图"""
    resource_type: ResourceType = ResourceType.MINDMAP
    mermaid_code: str = ""               # Mermaid 格式代码
    nodes: List[dict] = []               # 节点列表（用于前端渲染）


class VideoResource(LearningResource):
    """视频/动画资源"""
    resource_type: ResourceType = ResourceType.VIDEO
    duration_seconds: int = 60
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subtitles: Optional[str] = None


# ---- 学习路径 ----
class LearningStep(BaseModel):
    """学习路径中的一个步骤"""
    order: int
    title: str
    description: str
    knowledge_points: List[str]
    resources: List[str] = []             # 关联的资源ID
    estimated_time_minutes: int
    prerequisite_steps: List[int] = []    # 前置步骤


class LearningPath(BaseModel):
    """个性化学习路径 —— 对应赛题要求第3项"""
    path_id: str
    student_id: str
    course_name: str
    steps: List[LearningStep]
    total_time_hours: float
    generated_at: datetime = Field(default_factory=datetime.now)
    based_on_profile_version: int


# ---- 答疑 ----
class TutoringResponse(BaseModel):
    """智能辅导回复 —— 对应赛题要求第4项（加分）"""
    question: str
    text_answer: str                     # 文字解答
    diagram: Optional[str] = None        # 图解（Mermaid/图片URL）
    video_explanation: Optional[str] = None  # 短视频讲解URL
    related_knowledge: List[str] = []    # 关联知识点
    follow_up_questions: List[str] = []  # 建议追问


# ---- 评估 ----
class EvaluationResult(BaseModel):
    """学习效果评估 —— 对应赛题要求第5项（加分）"""
    student_id: str
    evaluation_time: datetime = Field(default_factory=datetime.now)
    dimensions: Dict[str, float]         # 各维度得分
    overall_score: float                 # 综合得分
    strengths: List[str]                 # 优势
    weaknesses: List[str]                # 薄弱点
    recommendations: List[str]           # 改进建议
    next_step_adjustment: Optional[dict] = None  # 路径调整建议
