<p align="center">
  <img src="docs/assets/repository-hero.svg" alt="智学领航——个性化学习多Agent平台" width="100%" />
</p>

# 智学领航——个性化学习多Agent平台

<p align="center">
  <strong>面向高校课程的企业级、可追溯、可恢复学习 Agent</strong><br />
  LangGraph orchestration · Hybrid RAG · Human review · Durable execution
</p>

<p align="center">
  <a href="https://github.com/a142269/evidence-first-learning-agent/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/a142269/evidence-first-learning-agent/ci.yml?branch=main&style=flat-square&label=CI" /></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.5-42B883?style=flat-square&logo=vuedotjs&logoColor=white" />
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-stateful_agent-1C3C3C?style=flat-square" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
</p>

---

## 项目概览

智学领航把课程问答、个性化讲解、练习生成与教师审核组织成一条可审计的学习工作流。每个回答都携带实际使用的来源；长任务通过 PostgreSQL 检查点和执行租约实现断线恢复；高风险内容在生成前拦截，需要人工确认的内容进入教师审核。

**旗舰链路是 V2 证据优先学习包**：受限规划与课程检索 → Tutor 讲解 → Practice 练习 → Reviewer 审查与最多一次返工 → 按需教师审核。V1 多角色对话是兼容和演示能力；辩论、多模态等属于实验功能，不代表 V2 的生产工作流。

V1 调度器按优先级分组并行执行；`depends_on` 是未执行的兼容字段，不提供 DAG 依赖调度。早期项目设计文档中的任务 DAG 属于规划，并非当前实现。

引用 ID 有效只说明来源存在，不能证明结论得到来源支持。[三组固定证据对照报告](evals/results/ablation-fixed-evidence-20261017.md)已记录 72 次真实模型运行及失败原因；双人质量复核尚未完成，不能据此声称多 Agent 优于单 Agent。逐条事实复核方法见 [评测计划](evals/CLAIM_AND_ABLATION.md)。

<p align="center">
  <img src="docs/assets/product-learning-package.png" alt="学习包生成页面" width="92%" />
</p>

| 核心能力 | 工程实现 | 可验证结果 |
| --- | --- | --- |
| Evidence-first RAG | pgvector + PostgreSQL FTS + RRF + 来源级去重 | 76 条新版 Golden Set 中 74 条通过 |
| Stateful Agent | LangGraph、PostgreSQL Checkpointer、SSE、执行租约 | 真实 PostgreSQL 恢复组合 15/15 |
| Tutor → Practice 学习包 | 受限检索决策循环、逐项引用、Reviewer 一次返工 | 13 个在线契约场景 13/13 |
| 生产权限边界 | 持久化令牌摘要、逐账号课程授权、V1 白名单 | SQLite / PostgreSQL 跨进程验证 |
| 异步知识摄取 | Celery、Redis、版本化文档、分块与向量重建 | 幂等、重投和租约接管测试 |
| 可观测与评测 | OpenTelemetry、Phoenix、预算守卫、数据集签名 | 可重放评测与用量审计 |

## 实测指标

以下结果来自 2026-10-16 的隔离测试环境。在线模型成绩与本地契约测试分开统计。

| 验证项 | 结果 |
| --- | ---: |
| 新版中文 Golden Set | **74 / 76（97.37%）** |
| 事实题 Hit@5 | **95.83%** |
| 事实题 Recall@5 | **94.79%** |
| 引用存在率 / 有效率 | **100% / 100%** |
| 本地离线测试 | **2153 passed, 18 skipped** |
| PostgreSQL 专项测试 | **15 / 15** |
| 学习包标准在线契约 | **13 / 13** |

评测口径、阈值和限制见 [evals/README.md](evals/README.md) 与 [实施状态](docs/UPGRADE_IMPLEMENTATION_STATUS.md)。

以上为历史测试汇总，不等于当前提交自动重跑的结果；[脱敏汇总和失败分析](evals/results/)不包含逐例原始报告，学习包在线契约也不等同人工内容质量评分。

## 系统架构

```mermaid
flowchart LR
    Student[学生 / 教师] --> UI[Vue 3 / Electron]
    UI --> API[FastAPI V1 + V2]
    API --> Auth[身份、课程授权、安全 Guard]
    Auth --> Graph[LangGraph EvidenceFirstGraph]
    Graph --> Tools[只读学习工具]
    Graph --> Retriever[Hybrid Retriever]
    Retriever --> Vector[(PostgreSQL + pgvector)]
    Retriever --> FTS[PostgreSQL FTS + RRF]
    Graph --> LLM[Provider Registry]
    Graph --> Review[教师审核 / 恢复]
    Graph --> Audit[(Run / Checkpoint / Audit)]
    Upload[教师资料] --> Celery[Celery Worker]
    Celery --> Vector
    Graph --> OTel[OpenTelemetry]
    OTel --> Phoenix[Phoenix]
```

### 学习问答状态机

```text
鉴权 → 安全判断 → 检索 → 画像上下文 → 生成 → 引用校验 → 持久化
```

学习包使用 Tutor → Practice 两步计划。模型只能选择 `search_course` 或 `finish`，最多检索三次；讲解和每道练习分别返回 `source_ids` 与结构化引用。交付状态区分 `completed`、`partially_completed`、`awaiting_approval`、`rejected`、`failed`、`interrupted`：只有通过 Reviewer 分项结论（以及按需教师审核）的内容才会交付，部分成功不会把未交付内容标记为已验证，详见 [学习包指南](docs/LEARNING_PACKAGE_GUIDE.md)。

## 产品界面

<table>
  <tr>
    <td width="50%"><img src="docs/assets/product-home.png" alt="Triple-U 登录页" /></td>
    <td width="50%"><img src="docs/assets/product-dashboard.png" alt="个性化学习工作台" /></td>
  </tr>
  <tr>
    <td align="center">六智能体角色与演示登录</td>
    <td align="center">个性化学习工作台与新手引导</td>
  </tr>
</table>

## 技术栈

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Celery, Redis
- **Agent:** LangChain, LangGraph, SSE, human-in-the-loop
- **RAG:** PostgreSQL, pgvector, HNSW, PostgreSQL FTS, RRF
- **Frontend:** Vue 3, TypeScript, Vite, Ant Design Vue, Electron
- **Observability:** OpenTelemetry, Phoenix, structured audit events
- **Delivery:** Docker Compose, GitHub Actions, Ruff, MyPy, Pytest

## 快速开始

### 1. 离线预览

离线模式不会调用付费模型 API。

```bash
git clone https://github.com/a142269/evidence-first-learning-agent.git
cd evidence-first-learning-agent
cp .env.example .env

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_demo
uvicorn backend.app.main:app --reload --port 8000
```

Windows / Python 3.12 可使用 `pip install -r requirements.lock.txt` 安装固定版本；该锁文件在 Windows 上解析并验证过定向测试。Linux / Python 3.12 使用已提交的 `requirements.lock.linux.txt`（uv 生成、带哈希，144 个包）：`python -m pip install --require-hashes -r requirements.lock.linux.txt`。nightly 的 `linux-lockfile` 任务会在 Ubuntu + Python 3.12 上按哈希安装该锁并运行核心学习包测试；如需重新生成（例如新增依赖后）使用 `uv pip compile --python-version 3.12 --python-platform linux --generate-hashes --no-header --output-file requirements.lock.linux.txt requirements.txt`。

另开一个终端：

```bash
cd frontend
npm ci
npm run dev
```

打开 <http://localhost:5173>，演示学生账号为 `demo-student-1`，访问密码为 `123456`。

### 2. 企业本地栈

需要 Docker Desktop。示例配置中的所有密钥均为空或为本地占位值。

```bash
cp .env.example .env
cp .env.enterprise.example .env.enterprise
docker compose --env-file .env.enterprise \
  -f docker-compose.yml \
  -f docker-compose.enterprise.yml \
  up -d --build
```

服务入口：

- Web：<http://localhost:5173>
- OpenAPI：<http://localhost:8000/docs>
- Phoenix：<http://localhost:6006>

## 验证

```bash
# 后端关键检查
ruff check --select=E9,F63,F7,F82 backend/app scripts tests
pytest tests/ --no-cov --benchmark-disable -q

# 前端
cd frontend
npm ci
npm run build
```

在线评测和向量回填可能产生第三方 API 费用。部分评测脚本提供预算守卫；固定证据对照采集脚本不设置费用上限，应由使用者自行控制服务商账户和账单。普通本地测试默认使用离线模式。

## 目录结构

```text
backend/app/
  agent_runtime/              # LangGraph、检查点、租约、学习包
  api/v2/                     # V2 认证、SSE、运行生命周期
  services/                   # 检索、摄取、向量重建、安全
  evaluation/                 # Golden Set 与学习包评测
frontend/src/                 # Vue 产品界面
alembic/versions/             # SQLite / PostgreSQL 数据迁移
evals/                        # 数据集、阈值和评测说明
scripts/                      # 回填、评测、运维与演示脚本
tests/                        # 单元、集成、PostgreSQL 恢复测试
docs/                         # 架构、权限、恢复与演示文档
```

## 深入阅读

- [企业架构实现指南](docs/ENTERPRISE_ARCHITECTURE_GUIDE.md)
- [V2 十模块实现说明](docs/V2_TEN_MODULE_IMPLEMENTATION.md)
- [Agent 十模块完备性评估与 Qwen 优化主计划（2026-10-19）](docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md)
- [Qwen ↔ Lead 协作对话（共享文件）](docs/QWEN_LEAD_DIALOGUE.md)
- [学习包设计与使用](docs/LEARNING_PACKAGE_GUIDE.md)
- [持久化认证与课程权限](docs/AUTH_AND_COURSE_ACCESS.md)
- [运行状态修复与断线恢复](docs/RUN_RECONCILIATION.md)
- [PostgreSQL 检查点验收](docs/POSTGRES_CHECKPOINT_ACCEPTANCE.md)
- [生产部署与安全边界](docs/PRODUCTION_DEPLOYMENT.md)
- [结构化输出诊断与复测（2026-10-18）](evals/results/structured-output-20261018.md)
- [第三方许可与素材说明](THIRD_PARTY_NOTICES.md)
- [5 分钟演示脚本](docs/DEMO_5_MINUTES.md)

## 安全说明

- 不提交 `.env`、API Key、访问令牌、供应商账单或在线评测原始输出。
- 生产模式默认要求身份认证和逐账号课程授权。
- V1 生产入口只开放经过审核的路由白名单。
- Agent 工具为只读集合；写入、发布、删除和外发操作会被拒绝。

## 许可证

项目代码采用 [MIT License](LICENSE)。第三方素材和依赖的许可条款以其各自声明为准。

---

<p align="center">Built as an auditable learning system where every answer can point back to evidence.</p>
