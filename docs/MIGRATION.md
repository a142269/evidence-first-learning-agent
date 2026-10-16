# 从 student-behavior-analysis → A3 多智能体学习系统 迁移指南

> 本文档记录从旧项目「基于多源数据的大学生行为分析与干预模型」向新赛题「A3-基于大模型的个性化资源生成与学习多智能体系统」的所有可复用经验、架构、代码模式的迁移映射。

---

## 一、两个项目的核心差异与衔接

| 维度 | 旧项目 (student-behavior-analysis) | A3 新项目 | 迁移策略 |
|------|-----------------------------------|-----------|---------|
| **数据来源** | 校园多源行为数据（一卡通、学习平台、图书馆等） | 用户通过对话输入 + 课程知识库 | 对话采集替代传感器采集 |
| **画像引擎** | 行为指标计算 → 5维画像（数值驱动） | 对话特征抽取 → 6维画像（NLP驱动） | 维度设计思想复用 |
| **模型层** | ML预测模型（风险预警） | LLM多智能体协同 | LLM替代传统ML |
| **内容生成** | 模板化报告 | 多模态学习资源 | 规则+模板的思路复用 |
| **交互方式** | Web看板 | 对话式 + 流式输出 | 前端交互提升 |

---

## 二、可复用内容清单

### 2.1 直接复用（无需改动）

#### 📁 项目目录结构模式
```
旧项目:                              新项目:
backend/                            backend/
  app/                                app/
    core/          ← 配置管理          core/
    repositories/  ← 数据访问          agents/       ← 多智能体
    schemas/       ← 数据模型          schemas/
    services/      ← 业务逻辑          services/
      features/    ← 特征工程          knowledge/    ← 知识库
      models/      ← 模型服务          utils/
      rules/       ← 规则引擎
    templates/     ← 报告模板          templates/
    utils/         ← 工具函数
  configs/         ← YAML配置          configs/
```

#### 📁 .env.example - 环境变量管理模式
- 旧项目：DATABASE_URL, SECRET_KEY 等敏感信息外置
- 新项目：完全相同的模式，添加 SPARK_API_KEY 等 LLM API 配置

#### 📁 .gitignore - 版本控制忽略规则
- 直接复用 Python + 环境变量的忽略模式

### 2.2 需要适配复用

#### 🧠 学生画像系统 → 对话式学习画像

| 旧项目组件 | 新项目对应 | 适配说明 |
|-----------|-----------|---------|
| 5维画像模型（学习投入、执行自律、作息规律、资源利用、身体发展） | 6维动态画像（知识基础、认知风格、易错点偏好、学习节奏、兴趣方向、能力短板） | 维度定义从行为域转向认知域 |
| `portrait.py` Schema 设计 | `learning_profile.py` Schema | Pydantic 结构完全复用 |
| 时间窗口滑动更新 | 随学随新动态更新 | 增量更新策略一致 |
| 个体画像 + 群体画像 | 个体画像 + 对比画像 | 双画像模式复用 |
| 分位排名对比 | 学习进度分位 | 统计方法复用 |

**关键迁移代码模式**：
```python
# 旧项目：基于行为指标构建画像
class BehaviorFeatureExtractor:
    def temporal_features(self, df):
        features[f'entropy_hour_{w}d'] = stats.entropy(hour_dist)
        return features

# 新项目：基于对话抽取特征 → 同样需要指标化
class DialogFeatureExtractor:
    def extract_knowledge_level(self, conversation_history):
        # 从对话中抽取知识基础指标，输出结构化数值
        return {"knowledge_score": 0.78, "level": "intermediate"}
```

#### 🔧 特征工程 → 对话特征抽取

| 旧项目 | 新项目 | 迁移点 |
|--------|-------|--------|
| `common_features.py` - 通用特征计算 | 通用对话指标计算 | 归一化、熵计算、统计函数复用 |
| `learning_behavior_features.py` | 学习行为模式识别 | 学习频率/持续性计算方法 |
| `volatility_features.py` | 学习状态波动检测 | 方差/突变检测算法 |
| `trend_features.py` | 学习趋势分析 | 斜率/回归方法 |

**可复用工具函数**：
```python
# 直接从旧项目迁移的通用工具
from app.utils.enums import IntEnum  # 枚举定义模式
from app.utils.metrics import calculate_entropy, calculate_slope  # 指标计算
from app.utils.dates import get_time_windows  # 时间窗口工具
```

#### 📊 规则引擎 → 多智能体协同规则

旧项目的 `rules/base_rule_engine.py` 设计模式可直接指导 Agent 间的协同规则：

```python
# 旧项目模式（规则驱动预警）
class RuleEngine:
    def evaluate_risk(self, student_features):
        rules = self.load_rules("intervention_rules.yaml")
        # if-then 规则匹配

# 新项目应用（规则指导Agent决策）
class AgentOrchestrator:
    def decide_next_agent(self, profile, user_intent):
        rules = self.load_rules("agent_routing.yaml")
        # 根据画像+意图选择下一步Agent
```

#### 📝 报告生成 → 智能辅导 + 学习效果评估

| 旧项目 | 新项目 | 迁移点 |
|--------|-------|--------|
| `SmartReportGenerator` (Jinja2 + LLM) | 多模态答疑回复 | 模板化生成 + LLM润色模式 |
| SHAP 归因解释 | 学习效果归因 | 贡献度分解思路一致 |
| `charts_config.json` - 图表配置 | 学习进度可视化 | 图表配置结构复用 |
| `student_report.docx` 模板 | 学习报告模板 | 模板设计思路 |

**归因解释模式迁移**：
```python
# 旧项目：SHAP归因解释
# "该生风险主要源于: (1)作业延迟率上升(贡献41%); (2)夜间活跃度增加(贡献27%)"
#
# 新项目：学习效果归因
# "该生当前学习瓶颈主要源于: (1)第3章概念理解偏差(贡献38%);
#  (2)第2-4节练习量不足(贡献25%); (3)知识点间关联建立不充分(贡献20%)"
```

#### 🔗 数据工程 → 知识库管理

旧项目的 ETL 管道经验迁移到知识库构建：

| 旧项目 ETL | 新项目知识库 | 迁移点 |
|-----------|-------------|--------|
| `source_tables.yaml` - 数据源配置 | 课程知识库配置 | YAML驱动配置模式 |
| `field_mapping.yaml` - 字段映射 | 知识点映射表 | 映射关系管理 |
| `quality_rules.yaml` - 数据质量规则 | 内容质量过滤规则 | 质量规则体系 |
| 数据清洗 pipeline | 文档预处理 pipeline | 处理流水线架构 |

### 2.3 架构设计经验（必须迁移）

#### 🏗️ 五层架构模式

旧项目技术方案中的分层架构可以直接指导 A3 系统设计：

```
旧项目:                             新项目 A3:
┌─────────────────┐                ┌──────────────────┐
│  展示层 (Vue3)   │     →         │  对话交互层 (Chat) │
├─────────────────┤                ├──────────────────┤
│  业务逻辑层      │     →         │  多智能体编排层    │
├─────────────────┤                ├──────────────────┤
│  AI/ML 模型层   │     →         │  大模型服务层      │
├─────────────────┤                ├──────────────────┤
│  数据计算层      │     →         │  知识计算层        │
├─────────────────┤                ├──────────────────┤
│  数据源层        │     →         │  知识库层          │
└─────────────────┘                └──────────────────┘
```

#### 🎯 可视化叙事模型（5层 → 5层）

旧项目的5层可视化叙事模型可以直接映射到学习路径展示：

| 旧项目五层 | A3学习路径叙事 | 复用 |
|-----------|---------------|------|
| 全局态势层 | 课程知识图谱全景 | 整体进度概览 |
| 群体结构层 | 知识点聚类分组 | 分组下钻逻辑 |
| 个体定位层 | 学生当前学习位置 | 雷达图展示 |
| 原因解释层 | 为什么跟不上/超前 | 归因分析 |
| 行动决策层 | 下一步学什么 | 路径推荐 |

---

## 三、核心代码模式移植

### 3.1 配置驱动架构（configs/）

旧项目的 YAML 配置模式直接复用：

```yaml
# configs/agents/resource_gen_agents.yaml
agents:
  doc_agent:
    name: "课程文档生成Agent"
    model: "spark-v4.0"
    prompt_template: "templates/doc_gen.jinja2"
    output_formats: ["markdown", "pdf"]
    
  mindmap_agent:
    name: "思维导图生成Agent"
    model: "spark-v4.0"
    prompt_template: "templates/mindmap_gen.jinja2"
    output_formats: ["mermaid", "png"]
    
  exercise_agent:
    name: "练习题生成Agent"
    model: "spark-v4.0"
    prompt_template: "templates/exercise_gen.jinja2"
    output_formats: ["markdown", "json"]
```

### 3.2 Schema 设计模式（schemas/）

```python
# schemas/profile.py - 复用旧项目 portrait.py 的设计思路
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class LearningDimension(BaseModel):
    """单个画像维度 - 必须数值化，不能只有标签"""
    name: str           # 维度名（如"知识基础"）
    score: float        # 0-1 得分
    level: str          # 等级标签
    evidence: List[str] # 支撑证据（来自对话）
    updated_at: datetime
    
class StudentProfile(BaseModel):
    """学生画像 - 复用旧项目5维→6维设计"""
    student_id: str
    dimensions: Dict[str, LearningDimension]  # 6+ 维度
    knowledge_graph: dict    # 已掌握知识点图
    learning_style: str     # 认知风格
    error_patterns: list    # 易错点
    goals: list             # 学习目标
    history: list           # 历史轨迹 ← 旧项目的轨迹存储
    created_at: datetime
    updated_at: datetime
```

### 3.3 多智能体编排（agents/）

```python
# agents/orchestrator.py
# 核心思路：复用旧项目 services 分层 + rules 规则引擎的协同模式

class AgentOrchestrator:
    """
    多智能体协同编排器
    
    灵感来源：
    - 旧项目 services/ 层的分层调用模式
    - 旧项目 rules/base_rule_engine.py 的规则驱动决策
    - 旧项目各个 service 之间的数据流转模式（schemas → service → repository）
    """
    
    def __init__(self):
        self.agents = {
            "profile": LearningProfileAgent(),
            "doc_gen": DocumentGenerationAgent(),
            "mindmap": MindMapAgent(),
            "exercise": ExerciseGenerationAgent(),
            "reading": ExtendedReadingAgent(),
            "video": VideoGenerationAgent(),
        }
        self.routing_rules = self._load_routing_rules()
    
    async def orchestrate(self, user_input, context):
        """根据用户意图 + 画像状态，决策调用哪些 Agent"""
        profile = await self.agents["profile"].get_or_update(context)
        
        # 规则驱动的路由 —— 复用旧项目规则引擎思想
        task_plan = self._plan_tasks(profile, user_input)
        
        # 并行调用多个资源生成Agent —— 来自旧项目并行服务调用经验
        results = await asyncio.gather(*[
            self.agents[name].generate(task)
            for name, task in task_plan.items()
        ])
        
        return self._merge_results(results)
```

### 3.4 知识库管理（knowledge/）

复用旧项目 ETL + 数据治理的经验：

```python
# knowledge/course_loader.py
# 借鉴旧项目 data_pipeline/etl_core.py 的设计

class CourseKnowledgeLoader:
    """
    课程知识库加载器
    
    迁移自旧项目:
    - StudentDataPipeline 的数据清洗规则引擎
    - source_tables.yaml → course_sources.yaml
    - 字段标准化 (standardization) → 知识点标准化
    """
    
    def __init__(self):
        self.clean_rules = self._load_quality_rules()  # 复用旧项目 quality_rules
        self.field_mapping = self._load_mapping()      # 复用旧项目 field_mapping
    
    def load_course(self, course_path: str):
        """加载一门课程的所有材料"""
        documents = self._parse_documents(course_path)
        cleaned = self._apply_clean_rules(documents)     # 旧项目 clean_rules 模式
        standardized = self._standardize_knowledge(cleaned)  # 旧项目标准化模式
        chunks = self._chunk_and_embed(standardized)
        return KnowledgeBase(course_name, chunks)
```

### 3.5 防幻觉 + 内容安全机制

借鉴旧项目的数据质量规则 + 预警规则引擎设计：

```python
# services/safety/content_filter.py
# 灵感来自旧项目 configs/data/quality_rules.yaml + rules/intervention_rules.yaml

class ContentSafetyChecker:
    """
    内容安全过滤 + 防幻觉机制
    
    设计迁移:
    - 旧项目: quality_rules.yaml 定义数据质量校验规则
    - 新项目: safety_rules.yaml 定义内容安全校验规则
    - 旧项目: 规则引擎的 if-then 链式评估
    - 新项目: 相同模式——链式过滤管道
    """
    
    def __init__(self):
        self.filters = [
            self._check_factual_accuracy,   # 事实准确性校验
            self._check_sensitive_content,  # 敏感内容过滤
            self._check_hallucination,      # 幻觉检测
            self._check_source_citation,   # 引用来源验证
        ]
    
    async def validate(self, content, knowledge_context):
        """复用旧项目规则引擎的链式评估模式"""
        for check in self.filters:
            result = await check(content, knowledge_context)
            if not result.passed:
                return result  # 快速失败
        return ValidationResult(passed=True)
```

---

## 四、A3 赛题 5 大功能与旧项目经验的对应

### 功能1：对话式学习画像自主构建

**旧项目经验来源**：`基于多源数据的学生画像生成与更新.md` + 5维画像模型

**关键迁移点**：
- 画像必须是"结构化数值"，不是文字描述
- 6个维度建议：知识基础、认知风格、易错点偏好、学习节奏、兴趣方向、能力短板
- 增量更新机制（对话即更新）
- 支持个体对比（与同级学生/目标水平对比）

**旧项目高分写法可直接改编**：
> "通过自然语言对话自动抽取特征，构建包含不少于6个维度的动态学生画像，支持随学随新，为后续个性化资源生成与路径规划提供基础支撑。"

### 功能2：多智能体协同的资源生成

**旧项目经验来源**：`技术方案.md` 的服务分层架构 + 服务间数据流转模式

**关键迁移点**：
- 至少5种资源类型：课程讲解文档、思维导图、练习题、拓展阅读、多模态教学视频/动画
- 5个Agent各自负责一种资源，Orchestrator统一调度
- 旧项目的 service 并行调用经验 → Agent 并行生成
- 流式输出（旧项目的实时数据处理经验 → 流式生成展示）

### 功能3：个性化学习路径规划

**旧项目经验来源**：`学业轨迹演化模式挖掘与关键行为分析.md`

**关键迁移点**：
- 旧项目的"学业轨迹"概念 → "学习路径"
- 时间序列分析 → 学习进度规划
- 拐点识别逻辑 → 学习瓶颈识别
- 模式分类 → 学习路径类型（速成型/稳扎稳打型/查漏补缺型）

### 功能4：智能辅导（可选加分）

**旧项目经验来源**：`基于归因解释与知识增强提示的个性化报告生成.md`

**关键迁移点**：
- 归因解释 → 答疑中的"为什么"解释
- 多模态回复：文字解答 + 图解 + 短视频
- 知识增强：课程知识库 + 常见错误库 = 精准答疑

### 功能5：学习效果评估（可选加分）

**旧项目经验来源**：`学业风险动态感知与预警模型构建.md`

**关键迁移点**：
- 风险动态感知 → 学习效果动态跟踪
- 滑动时间窗口 → 学习周期评估
- 多指标评估 → 多维学习效果评估
- 评估驱动干预 → 评估驱动学习路径调整

---

## 五、技术栈对照与升级

| 旧项目技术 | A3 新项目技术 | 策略 |
|-----------|-------------|------|
| Python 后端 | Python 后端 | 语言不变 |
| FastAPI | FastAPI + WebSocket | 框架复用，加 WebSocket 支持流式 |
| SQLAlchemy + PostgreSQL | SQLite/PostgreSQL + ChromaDB | 关系库 + 向量库 |
| scikit-learn + XGBoost | 科大讯飞 Spark API | ML → LLM |
| YAML 配置 | YAML 配置 | 完全复用 |
| Jinja2 模板 | Jinja2 提示模板 | 模板引擎复用 |
| ECharts 可视化 | ECharts + Markdown渲染 | 技术栈延续 |
| Docker Compose | Docker Compose | 完全复用 |

---

## 六、20天时间线与旧项目加速效果

借鉴旧项目开发节奏，以下流程因复用经验而缩短：

| 阶段 | 不借鉴需时 | 借鉴后需时 | 加速来源 |
|------|-----------|-----------|---------|
| 项目架构搭建 | 2天 | 0.5天 | 目录结构、配置模式直接复用 |
| 数据层（知识库） | 3天 | 1.5天 | ETL + 数据治理模式复用 |
| 画像模块 | 4天 | 2天 | 5维画像设计直接升级为6维 |
| 多智能体模块 | 6天 | 3天 | service分层+规则引擎思路复用 |
| 路径规划 | 3天 | 1.5天 | 轨迹分析 → 路径规划映射 |
| 前端+交互 | 4天 | 2天 | 可视化叙事5层模型复用 |
| 测试+文档+录制 | 5天 | 3天 | 旧项目文档规范复用 |
| 缓冲 | 3天 | 3天 | — |
| **合计** | **30天** | **16.5天** | **节省约45%** |

---

## 七、迁移检查清单

- [ ] 创建 A3 项目目录结构（参考旧项目 backend/app/ 分层）
- [ ] 配置 .env.example + configs/ 目录
- [ ] 实现 6维学习画像 Schema + 对话特征抽取
- [ ] 搭建多智能体框架（Orchestrator + 5 Agent）
- [ ] 对接科大讯飞 Spark API
- [ ] 构建至少1门课程知识库
- [ ] 实现5种资源生成 Agent
- [ ] 实现学习路径规划算法
- [ ] 前端对话界面 + 流式输出 + Markdown 渲染
- [ ] 防幻觉 + 内容安全过滤机制
- [ ] Docker 部署配置
- [ ] 演示PPT + 7分钟视频 + 配套文档
