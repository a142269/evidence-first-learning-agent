# Triple U 平台简明技术架构图

> 用途：报告与 PPT 展示。仅保留平台的关键层次和核心数据流，不展开具体算法、校验与内部实现。

```mermaid
flowchart TB
    USER["用户端<br/>学生 · 教师/管理员"]

    subgraph CLIENT["多端应用"]
        WEB["Web 前端<br/>Vue 3"]
        MOBILE["移动端<br/>消息 · 错题 · 资源"]
        DESKTOP["桌面端<br/>Electron"]
    end

    FRONT["前端交互层<br/>学习、教学管理、群聊、桃园学宫"]

    subgraph BACKEND["后端服务层 · FastAPI"]
        BIZ["核心业务服务<br/>账号、学习路径、错题、资源、教学管理"]
        REALTIME["实时交互服务<br/>群聊与流式回复"]
    end

    subgraph AI["AI 智能引擎"]
        AGENT["多智能体协作<br/>规划 · 讲解 · 出题 · 生成 · 评估 · 守护"]
        MODEL["大模型与多模态生成<br/>文本 · PPT · 导图 · 音频 · 视频"]
    end

    subgraph DATA["数据与知识层"]
        LEARNING["学习数据<br/>用户 · 画像 · 路径 · 错题 · 评估"]
        KNOWLEDGE["课程知识库<br/>知识图谱 · 向量索引"]
        RESOURCE["资源与产物库<br/>课程资料 · AI 生成资源"]
    end

    USER --> WEB
    USER --> MOBILE
    USER --> DESKTOP
    WEB --> FRONT
    MOBILE --> FRONT
    DESKTOP --> FRONT
    FRONT <--> BIZ
    BIZ <--> REALTIME
    BIZ <--> AGENT
    AGENT <--> MODEL
    BIZ <--> LEARNING
    BIZ <--> KNOWLEDGE
    BIZ <--> RESOURCE
    AGENT <--> KNOWLEDGE
    MODEL --> RESOURCE

    classDef user fill:#FFF4DB,stroke:#C79028,stroke-width:2px,color:#362300;
    classDef client fill:#EAF4FF,stroke:#4586C6,stroke-width:2px,color:#0B3157;
    classDef frontend fill:#EAF8F1,stroke:#3B9A6A,stroke-width:2px,color:#173E2B;
    classDef backend fill:#F0ECFF,stroke:#775FC2,stroke-width:2px,color:#2B1D5A;
    classDef ai fill:#FFF0EC,stroke:#D76B45,stroke-width:2px,color:#59220F;
    classDef data fill:#F5F5F5,stroke:#7A7A7A,stroke-width:2px,color:#222;
    class USER user;
    class WEB,MOBILE,DESKTOP client;
    class FRONT frontend;
    class BIZ,REALTIME backend;
    class AGENT,MODEL ai;
    class LEARNING,KNOWLEDGE,RESOURCE data;
```

## 图示说明

- 多端应用统一访问 Vue 前端和 FastAPI 后端；Electron 复用同一套应用。
- 后端负责账号、学习、资源、教学管理及实时聊天等核心业务。
- 多智能体调用大模型与多模态生成能力，并根据课程知识库提供个性化服务。
- 学习数据、课程知识和生成资源统一沉淀，持续支持学习路径、画像与教学决策。
