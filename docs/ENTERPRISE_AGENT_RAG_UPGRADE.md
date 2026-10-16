# Triple-U 企业级 Agent / RAG 升级记录

> 分支：`feat/enterprise-agent-rag-stack`  
> 更新日期：2026-10-12
> 目标：把原有多 Agent 学习系统升级为可演示、可追溯、可评测的企业级 Agent / RAG 项目，为求职作品集做准备。

## 1. 当前结论

项目的**核心旗舰链路已经可运行并完成真实验收**：

```text
教师上传资料
  → Celery 异步解析 / KnowledgeGuard 审核
  → Qwen 云端 Embedding
  → PostgreSQL + pgvector 存储文档版本与向量
  → pgvector 稠密检索 + PostgreSQL 全文检索 + RRF 融合
  → LangGraph 学习问答流程
  → 引用、人工审核中断/恢复、审计与 Phoenix 观测
```

该链路已具备“可用、可解释、可回退”的工程基础；66 条 Golden Set 已完成真实在线验收，核心契约已接入 CI，README、5 分钟演示脚本与求职材料包已经补齐。它仍不是“所有旧 Agent 全部迁入 LangGraph”的重写项目；当前旗舰链路和后续边界见[架构实现指南](ENTERPRISE_ARCHITECTURE_GUIDE.md)。

## 2. 已完成的工作

### 2.1 Git 同步与工作区保护

- 使用 `feat/port-react-companion-to-vue` 作为整合主线，同步远端并合并 `origin/main`，保留 merge 历史。
- 为同步前改动创建 WIP 分支：`wip/pre-sync-20261010`。
- 本地产物、上传文件和运行目录不纳入正式提交；运行中生成的 `data/rag/knowledge_index.json` 保持本地状态。
- 升级工作在独立分支 `feat/enterprise-agent-rag-stack` 完成。
- 未向 GitHub 推送任何升级提交或敏感配置。

### 2.2 企业级本地运行环境

新增 `docker-compose.enterprise.yml`，通过 Docker Compose 启动以下服务：

| 服务 | 作用 | 本地端口 |
| --- | --- | --- |
| Backend | FastAPI、V1/V2 API、LangGraph 运行时 | `8000` |
| Frontend | Vue + Nginx 反代 | `5173` |
| PostgreSQL + pgvector | 业务数据、向量、检查点、审计 | `5432` |
| Redis | Celery Broker / Result Backend | `6379` |
| Celery Worker | 异步文档摄取任务 | 内部服务 |
| Phoenix | OpenTelemetry Trace 查看 | `6006` |

已修复容器运行问题：

- 前端健康检查由错误端口改为 Nginx 实际监听端口。
- Celery 健康检查改为经 Redis `inspect ping` 验证。
- Nginx 改用 Docker 内置 DNS 动态解析 Backend，避免后端重启换 IP 后前端持续返回 `502 Bad Gateway`。

### 2.3 安全与工程底座

- 移除了代码中默认注入的模型密钥路径，运行密钥仅从环境变量/部署密钥读取。
- 提供 `.env.enterprise.example`；真实 `.env.enterprise` 不进入版本控制。
- GitHub Actions 已包含：Gitleaks 秘密扫描、`pip-audit` 依赖漏洞扫描、Ruff、Mypy、Alembic 迁移冒烟与 pytest。
- 新增 Alembic 企业数据模型迁移，包含文档版本、文档切片、向量、检索日志、Agent Run、检查点和评测结果表。
- SQLite 保留为旧版离线演示和 RAG 降级数据源；PostgreSQL/pgvector 为 V2 旗舰链路的数据源。

> 注意：若历史提交中出现过真实 API Key，必须在供应商控制台**撤销并轮换**。这一步只能由密钥账户持有人操作。

### 2.4 LangGraph + Harness 旗舰链路

实现 `/api/v2/learning-runs/stream` SSE API，固定事件包括：

```text
run.started
retrieval.completed
answer.delta
review.required
run.completed
run.failed
```

核心实现：

- `EvidenceFirstGraph` 采用 LangGraph `StateGraph`：检索 → 生成 → 人工审核（可选）→ 引用校验。
- 使用 PostgreSQL Checkpointer 持久化线程状态，并支持人工审核后恢复执行。
- 高风险请求可触发 `review.required`，审核拒绝时不会返回原始检索证据，避免信息泄露。
- 定义 Harness 契约：`RunContext`、`RunPolicy`、`RunResult`，便于后续增加预算、超时、工具白名单与评测。
- Agent Run、节点状态、检查点持久化到 PostgreSQL，便于审计和演示恢复能力。

### 2.5 异步摄取、云端 Embedding 与 pgvector

教师上传资料后：

1. 文件先进入暂存目录。
2. Celery Worker 执行解析、KnowledgeGuard 审核、旧 RAG 索引更新。
3. 创建 `document_versions` 父记录。
4. 分块后按 Provider 限制批量调用 OpenAI-compatible Embedding API。
5. 将 1024 维向量写入 `document_chunks.embedding`。

当前云端配置使用：

```text
模型：qwen3.7-text-embedding
维度：1024
批量上限：20
协议：OpenAI-compatible Embeddings API
```

已修复 PostgreSQL 外键顺序问题：在写入 `document_chunks` 前显式 `flush()` 文档版本父记录；并补充回归测试。

### 2.6 企业检索与引用

V2 学习问答优先走 `EnterpriseRetriever`：

- Qwen 将用户问题转换为查询向量。
- pgvector 以余弦距离召回稠密候选。
- PostgreSQL `tsvector` 全文检索召回词法候选。
- 采用 Reciprocal Rank Fusion（RRF）融合两套排序。
- 返回内容、来源、课程、chunk ID、分数与检索器标识，供 LangGraph 引用节点生成可验证引用。
- 云端 Embedding / PostgreSQL 不可用时，自动回退到 V1 SQLite RAG，避免演示不可用；两套索引同时可用时以 RRF 融合，避免少量新上传资料遮蔽内置课程章节。
- 内置课程 Markdown 可通过 `scripts/backfill_enterprise_corpus.py` 迁入同一版本化 pgvector 索引；教师上传资料仍保留 Celery 审核与异步摄取路径。融合阶段按来源去重，避免同一份资料在 V1/V2 双索引中重复挤占 Top-K。

## 3. 已完成的真实验收

### 3.1 服务健康

以下 Compose 服务曾验证为健康或运行中：

```text
a3-backend               healthy :8000
a3-frontend              healthy :5173
triple-u-celery-worker   healthy
triple-u-postgres        healthy :5432
triple-u-redis           healthy :6379
triple-u-phoenix         running :6006
```

### 3.2 LangGraph 审核与恢复

- V2 SSE 正常输出 `run.started`、`retrieval.completed`、`answer.delta`、`run.completed`。
- PostgreSQL 中已验证 `agent_runs`、`agent_checkpoints` 与 LangGraph 的 `checkpoints` 相关表。
- 人工审核拒绝后，系统仅返回“未通过人工审核”的安全结果，`citations`、`evidence` 均为空。

### 3.3 文档向量化

上传 `cloud-embedding-smoke.md` 后，数据库真实查询结果：

```text
document_versions：2 条 indexed 版本
document_chunks：2 个分块
embedding 非空：2 个分块
vector_dims(embedding)：1024
```

### 3.4 pgvector 检索

针对“qwen3.7-text-embedding 会把中文课程片段转换成多少维向量？”进行容器内检索，结果为：

```text
count: 2
retriever: pgvector_hybrid_rrf
source: artificial_intelligence/uploads/cloud-embedding-smoke-*.md
```

并命中“转换为 1024 维向量”的原始上传内容。

### 3.5 Golden Set 最终候选基线（2026-10-11）

在演示学生身份认证、Qwen 云端 Embedding 和 pgvector 课程资料回填完成后，完整 66 条中文 Golden Set 的真实结果为：

```text
通过：64 / 66（96.97%）
Recall@5：95.83%（门槛：85%）
引用完整性：100%（门槛：100%）
安全与人工审核：100%（门槛：100%）
平均端到端耗时：9,100.91 ms
```

`reports/golden_set_candidate_baseline.json` 是该次运行的本地候选报告。仅有 `qa-008`、`qa-027` 未命中 Golden Set 指定的来源；二者均有可验证引用，因此不影响既定质量门禁，但保留为后续中文 reranker 与章节路由的回归用例。

评测执行器会对临时 SSE 连接/读取超时自动重试一次；每次请求使用独立 LangGraph thread ID，避免人工审核 checkpoint 在重试之间串扰。

## 4. 关键本地提交

| Commit | 说明 |
| --- | --- |
| `cf8eaa5` | Evidence-first Agent Runtime V2 |
| `e49f0b3` | 企业 RAG 平台基础 |
| `4620f60` | 企业数据库迁移 |
| `ee50ef0` | LangGraph Run 与 Checkpoint 持久化 |
| `018d075` | 人工审核 LangGraph 中断与恢复 |
| `4465161` | 云端 Embedding 摄取基础 |
| `5bb0fcb` | 云端 Provider 批量限制 |
| `07d91e2` | 前端 Nginx 动态解析 Backend |
| `5b5d6f8` | 文档版本先 flush 再写入向量分块 |
| `8ee7e26` | 教师端轮询 Celery 异步摄取任务 |
| `2dfa07f` | pgvector + PostgreSQL FTS + RRF 检索 |
| `9fc5931` | 内置课程资料回填 pgvector、来源级 RRF 去重、人审前置中断 |
| `654c697` | Golden Set 临时 SSE 超时重试与隔离的评测线程 |

## 5. 当前限制与风险

1. PostgreSQL `simple` 全文检索对中文分词能力有限；下一阶段应接入中文 reranker 或专门的中文全文检索策略。当前 Golden Set 的 `qa-008`、`qa-027` 保留为该改进的回归样本。
2. BGE-M3 本地 Embedding 与本地 reranker 尚未接入；当前选择云端 Qwen 以降低本地内存和磁盘成本。
3. V2 已覆盖认证身份覆盖、课程白名单、提示注入拒答与高风险人审；真实部署仍须将演示会话和环境变量课程白名单替换为持久化 IdP 与选课关系表。
4. CI 已验证全新 PostgreSQL/pgvector 迁移及关键契约测试；Docker 端到端摄取、SSE 审核恢复和完整 Golden Set 在线评测仍适合保留为受控的夜间/发布前作业，以避免每次 PR 产生云端模型成本。

## 6. 下一步工作（按优先级）

### P0：发布前安全收口

- 在模型供应商平台撤销并轮换可能暴露过的 API Key。
- 确认 `.env.enterprise` 从未加入 Git；推送前运行 Gitleaks。
- 增加 `.env` 配置校验：生产模式缺少模型密钥、数据库密码或允许来源时应拒绝启动。

### P1：Golden Set 与自动评测（已达标，持续维护）

- 已新增 66 条中文 Golden Set，覆盖：课程问答、跨章节、无答案、引用完整性、提示注入、课程/角色隔离、画像个性化、人工审核。
- 已实现离线/在线评测脚本，输出 Recall@5、引用完整性、安全与人审通过率、平均延迟和逐例结果；在线模式调用 V2 SSE，离线模式可复用保存的预测结果，不必重复消耗模型额度。
- 评测说明与 CMD 命令见 `evals/README.md`。首次在线执行会调用云端模型，应先人工审阅结果；不要为了让门禁变绿而删除失败安全用例。
- 设定门禁：安全与权限用例 100%；事实回答引用完整性 100%；Recall@5 ≥ 85%；相对基线不回退超过 3 个百分点。2026-10-11 的候选基线为 64/66、Recall@5 95.83%、引用与安全/人审均 100%。

### P2：检索质量增强

- 接入中文 reranker，并在 Golden Set 中比较“仅稠密检索 / RRF / RRF + Reranker”。
- 对中文全文检索引入适合中文的分词策略，或以 reranker 补强 FTS 的不足。
- 实现文档替换/版本选择策略，使同一教师资料升级时形成明确的版本关系。
- 为每个事实性结论建立更严格的“答案句子 ↔ 来源片段”映射，而不仅是回答末尾列出引用。

### P3：安全、权限与可观测性验收

- V2 已增加检索前安全策略节点：提示注入、系统提示词/私有资料索取、危险外部操作、试卷答案和医疗处方类请求会在进入检索与模型前被拒绝。
- Enterprise Compose 已默认启用 V2 Bearer Session 身份认证；服务端以认证账户覆盖请求体的 `user_id`，拒绝身份伪造，并按服务端课程白名单限制学生访问。教师可跨课程访问。真实部署仍应将演示会话替换为持久化身份提供商与选课关系表。
- 添加课程级权限过滤、越权访问、恶意附件、提示注入与审核绕过的集成测试。
- 验证 Phoenix 中能够看到 Graph 节点、Embedding、检索、模型、人工审核、失败与耗时 Trace。
- 记录模型调用成本、Embedding 成本、检索耗时与审核等待耗时，区分系统耗时和人工等待时间。

### P4：CI 企业质量门禁

- CI 已增加 PostgreSQL/pgvector/Redis Service 容器，并在全新 PostgreSQL 中执行 Alembic 迁移、验证 pgvector 扩展、运行 V2 身份/安全/检索/Golden Set 契约测试。
- 增加 Docker 冒烟、Celery 摄取、SSE 契约、审核恢复、RAG 评测与安全回归作业。
- 失败时上传评测 JSON、JUnit/XML 或 Markdown 报告作为构建产物。

### P5：求职交付物

- 更新 README：架构图、快速启动、模型切换、环境变量说明、真实评测指标、成本/延迟、故障恢复演示。
- 完成 ADR：LangGraph 选型、pgvector 选型、OTel + Phoenix 选型。
- 准备 5 分钟演示：教师上传 → 异步入库 → 可追溯问答 → 人工审核恢复 → Phoenix Trace → 评测报告。
- 输出简历项目描述、STAR 项目故事和高频面试题库，突出“生产化 Agent 系统”而非框架堆砌。

## 7. 常用本地命令

启动企业环境：

```cmd
docker compose --env-file .env.enterprise -f docker-compose.yml -f docker-compose.enterprise.yml up --build -d
```

查看服务状态：

```cmd
docker compose --env-file .env.enterprise -f docker-compose.yml -f docker-compose.enterprise.yml ps
```

查看 Worker 摄取日志：

```cmd
docker compose --env-file .env.enterprise -f docker-compose.yml -f docker-compose.enterprise.yml logs worker --tail=100
```

验证 pgvector 写入：

```cmd
docker compose --env-file .env.enterprise -f docker-compose.yml -f docker-compose.enterprise.yml exec postgres psql -U triple_u -d triple_u -c "SELECT vector_dims(embedding) AS dimension, COUNT(*) AS vectors FROM document_chunks WHERE embedding IS NOT NULL GROUP BY vector_dims(embedding);"
```

## 8. 安全约定

- 不要把 `.env.enterprise`、API Key、数据库密码、访问令牌粘贴到聊天或提交到 Git。
- 不要推送本分支，直到完成密钥轮换、Gitleaks 检查与人工复核。
- Docker 镜像、卷和 WSL 虚拟磁盘默认可能占用 C 盘；项目源码仍位于 D 盘。
