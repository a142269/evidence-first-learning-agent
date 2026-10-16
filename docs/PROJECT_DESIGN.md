# A3-Learning-Agent-System: 项目技术与架构设计

## 项目背景
本项目为第十五届“中国软件杯”A3赛题：**基于大模型的个性化资源生成与学习多智能体系统开发** 的参赛作品核心仓库。

## 架构底座 (资产复用)
本项目是在已有现代化全栈系统（`student-behavior-analysis`）的基础上孵化而来，最大化复用了其健壮的基础设施：
1. **FastAPI 后端引擎**：采用异步架构与成熟的中间件/鉴权设计。内置了 SSE（Server-Sent Events）流式大模型对话接口与 RAG 知识库检索服务。
2. **Vue3 + Vite 前端框架**：基于 TypeScript、Vue Router 和 ECharts 构建，保留了高度可定制化的组件库与灵活的网络请求封装。

## 多智能体协同框架设计 (Multi-Agent Architecture)
为了满足赛题要求，后端的 `qa.py` 已被重构为 `agents.py`，作为多智能体调度的核心入口：
1. **学生画像提取智能体 (Profile Agent)**：通过自然语言交互（如“我最近学习有点吃力”）自动提取特征，动态构建6维度以上的学生画像。
2. **资源生成智能体协作网络 (Resource Generators)**：
   - *课件生成智能体*：自动生成 PPT 骨架和内容。
   - *多模态扩展智能体*：寻找/生成对应的音视频或图解。
   - *测评生成智能体*：针对短板生成巩固题库。
3. **学习路径规划智能体 (Path Planner Agent)**：融合画像与生成资源，提供因材施教的递进式学习计划。

## 后续开发计划
1. **大模型底座切换**：赛题要求使用科大讯飞相关工具。我们将平滑迁移当前的 `ModelScopeLLMClient` 为 `SparkLLMClient`（讯飞星火 API）。
2. **前端重构**：将旧的“数据监控大屏”重写为“个性化交互式学习面板”，分为交互聊天区、生成资源展示区与学习路径规划区。
3. **知识库挂载**：引入我们沉淀的《高校学生行为与就业去向专家知识库》作为初始化专业课程知识库。

---
*Created automatically during initial project migration & scaffolding.*
