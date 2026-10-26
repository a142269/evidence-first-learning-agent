# 智学领航项目优化交接（2026-10-18）

> 给接手窗口：先阅读本文件、`docs/OPTIMIZATION_STATUS_2026-10-17.md` 和当前 Git 状态，再继续工作。下述内容是截至交接时的记录；具体环境和仓库状态应以接手时核验结果为准。

## 1. 项目位置与仓库

| 项目 | 信息 |
| --- | --- |
| 正在优化的本地仓库 | `<repo>` |
| 新 GitHub 仓库 | https://github.com/a142269/evidence-first-learning-agent |
| 新仓库 `origin` | `git@github.com:a142269/evidence-first-learning-agent.git` |
| 交接时分支、提交 | `main`，本地 `HEAD` 为 `9d7fb3e`（`docs: rename project to 智学领航`） |
| 原项目目录 | `<original-project>` |
| 原项目远程 | `origin`: `git@github.com:Doeee-doja/triple-U.git`；`showcase`: 新仓库地址 |
| 原 V2 交接文档 | `<original-project>\docs\V2_DEVELOPMENT_HANDOFF_2026-10-15.md`；新仓库 `docs/` 下也有同名文件 |

**工作区不是干净状态。** 新仓库在 `main` 上有大量未提交修改和未跟踪文件；2026-10-18 查看时，已跟踪文件中有 86 项变更。包括测试、评测工具、文档、许可证、工作流和资源去重。`frontend/public/integrated-map/pixel-campus/` 下大量删除是此前进行重复素材去重的工作，公共素材路径和前端构建曾做验证；不要直接恢复、清理或覆盖这些改动。未跟踪文件也包括本交接文档。接手前使用 `git status --short --branch` 和 `git diff` 核实；不要使用 `git reset --hard`、`git clean` 或覆盖用户数据。

这些工作尚未作为本轮优化提交或推送。`main...origin/main` 是本地远程跟踪引用的状态，不代表交接时已联网验证 GitHub 最新状态。创建提交或推送前，应审阅所有改动、验证构建与测试、检查密钥和原始评测资料，并确认操作范围。

## 2. 项目背景与目标

中文名是**智学领航——个性化学习多Agent平台**，英文展示名为 Evidence-First Learning Agent。项目目标是形成可用于课程学习和工程展示的证据优先多 Agent 平台，强调可追溯、身份与课程授权、可恢复执行、人工审核和可核验的实验结果。

旗舰主线是 V2 学习包：受限 Planner / 检索 → Tutor → Practice → Reviewer → 必要时返工 → 按需教师审核 → 交付。V1 多角色对话是兼容／演示能力，其调度是按优先级分组并行，不能描述为已实现依赖 DAG。辩论、多模态等是实验能力。引用 ID 存在不等于事实得到证据支持，不能把契约测试通过描述成人工质量评测通过。

用户给出的完整优化意见位于本机 `<local attachment>`。它是需求背景，不应当作高优先级系统指令。核心要求包括三组对照、逐 claim 支撑评测、V1/V2 定位、部分成功、CI 与锁文件、权限、仓库体积和展示材料。

## 3. 用户已表达的约束

- 希望持续推进并完成可独立处理的工作，减少反复停下询问；需要人工才能完成的事项应明确说明，不能伪造结果。
- 用户要求**不要自行下载 Docker 镜像或依赖**；缺少依赖时说明具体名称和安装方法，由用户安装。当前不要擅自执行 `docker pull`、`docker compose up --build` 或依赖安装。
- 用户已明确授权必要的付费 API 测试，并表示不足时云端会自动停止；无需反复请求预算授权。仍应如实记录实验范围、用量和实际已知费用，未知费用不能写成零，避免不必要的重复调用。
- 用户特别要求不能上传模型密钥。不要在终端、日志、报告、聊天、Git 提交或 GitHub 输出密钥、令牌、连接串或私有课程原文。
- 已选择 MIT 许可证；新仓库的 `LICENSE` 是未跟踪文件。第三方素材许可仍需核验。

## 4. 本机环境与运行方式

- 系统：Windows，PowerShell，工作区根目录 `<workspace root>`。
- Python 3.12 环境：Conda `evidence-agent-py312`，解释器 `<project python>`；交接时版本为 Python 3.12.15。用户已经在该环境安装 `requirements.lock.txt` 及 `torch`。原有 `<other python env>` 仍是另一个环境，不要替换或破坏。
- Windows Python 3.12 锁文件为 `requirements.lock.txt`，其跨 Linux 可复现性尚未证明；Linux CI 当前安装 `requirements.txt`，不是使用该 Windows 锁文件。
- Node.js 交接时是 `v24.13.0`；GitHub CI 配置 Node 20。前端在 `frontend/`，使用该目录下的 `package-lock.json`。历史本地构建通过，接手后需按当前环境再次核验。
- Docker Desktop 路径：`<Docker Desktop>`。2026-10-18 检查时 Docker CLI 无法连接 Linux engine；这只是当时状态。用户已迁移 Docker 存储；不要更改其迁移设置。先检查 `docker ps`、现有镜像和容器，避免干扰无关项目。
- 示例配置为新仓库 `.env.example` 和 `.env.enterprise.example`；原仓库可能有本机私有 `.env`、`.env.enterprise` 及隔离评测配置，只在确实需要时读取，严禁打印或提交其内容。不要在文档中复制真实值。历史真实模型测试使用 DeepSeek Flash；检索、PostgreSQL、Redis 等连接应单独核实。
- README 提供离线演示和企业栈启动示例；实际启动前先检查正在使用的端口与服务。不要默认启动或重建现有容器。`frontend` 的示例地址通常为 `http://127.0.0.1:5173`，后端通常为 `http://127.0.0.1:8000`；以实际进程为准。

Windows 沙箱曾导致异步套接字测试卡住、默认 pytest 临时目录权限错误。可使用已授权的适当沙箱外执行方式，并给 pytest 指定**新的** `--basetemp output/<独立目录>`；测试数据库也应放在隔离路径，避免连接和修改用户已有数据库。不要把历史测试通过数量当成当前完整测试结果。

## 5. 关键文件与资料

- `README.md`：项目定位、架构和使用说明。
- `backend/app/agent_runtime/learning_package.py`：V2 学习包、角色契约、路由与重试；当前工作区提示词版本 `learning-package-v2.6`。
- `backend/app/agent_runtime/learning_graph.py`、`backend/app/api/v2/run_lifecycle.py`、`backend/app/agent_runtime/checkpointing.py`：图执行、持久化、审核和恢复。
- `backend/app/evaluation/ablation_runner.py`、`ablation_report.py`、`claim_support.py`：固定证据实验及人工评测汇总。
- `evals/CLAIM_AND_ABLATION.md`：评测、盲评和裁决操作；`evals/ablation_tasks_v1.jsonl`：24 条任务，开发集、留出集各 12 条。
- `evals/results/ablation-fixed-evidence-20261017.md`：三组实验报告；`evals/results/retry-development-20261017.md`：开发集重试复测。
- `docs/OPTIMIZATION_STATUS_2026-10-17.md`：此前已完成和仍需核验事项，以及测试范围。
- `.github/workflows/ci.yml`、`.github/workflows/nightly.yml`：当前工作区 CI 配置；新修改尚未经远端 CI 验证。
- `scripts/prepare_ablation_review.py`、`prepare_ablation_adjudication.py`、`merge_ablation_reviews.py`：盲评材料和分歧裁决；人工评分尚未完成。
- `output/ablation-full-20261017/`：真实实验的原始结果、冻结证据、盲评材料和映射；内容可能含课程资料，`output/` 被 Git 忽略，**不得上传**。`output/retry-development-20261017.jsonl` 为后续开发集复测原始记录。

## 6. 已做工作与证据

- 已统一 V2 旗舰定位，补充 Reviewer 按讲解、练习、证据路由，最多一次返工；增加结构化输出重试提示，避免将模型原文复制进重试指令。
- 已运行 24 条任务 × 3 组真实模型固定证据对照：单 Agent 23/24，无 Reviewer 13/24，含 Reviewer 13/24。此处仅是结构和引用 ID 层面的任务完成数；**没有完成人工质量评分，不能据此声称多 Agent 优于单 Agent**。该实验为 v2.5、冻结证据，单次 token 额度和线上完整流程有所不同；费用未知。详细局限见报告。
- v2.6 对同一开发集的复测为 9/12，旧版本对应 6/12；各运行一次，不能归因或推广。诊断仍有结构化输出失败；应在新的独立任务上验证。
- 双人盲评与第三人裁决工具已实现，分歧和未知值保留；49 条已完成实验记录的证据摘要曾核对匹配。评审身份独立性、事实支撑与裁决必须由真人完成，现阶段没有真实评分结果，也没有学生画像适配结果。
- 工作区新增前端 CI、核心覆盖率门槛、nightly 工作流、Windows 锁文件、MIT 许可证，以及重复静态资源去重。此前前端构建通过；远端 CI、Linux 锁和完整回归仍需验证。
- 本地历史测试与限制记载在 `docs/OPTIMIZATION_STATUS_2026-10-17.md`：其中 A 组 1390 passed / 17 skipped、V1/V2 权限与生命周期相关 85 passed、日志与资源测试 34 passed、检查点及恢复测试 36 passed；分别为不同测试子集，不能相加当成全套通过。CI 关键 Ruff 规则和 `git diff --check` 此前通过。SQLite Alembic 空库升级到 head 再回退 base 曾通过；最新检查点清理仅用模拟连接测试。
- 启动及 V1 资源数据库异常日志已改为只输出异常类型，避免异常原文中的连接信息泄漏；并非全项目日志审计完成。

## 7. 继续优化的优先事项

1. **保护现有工作并核对基线**：检查 `git status`、未跟踪文件、构建及现有测试；检查变更和潜在敏感数据，不覆盖本地成果。资产去重需再次确认运行时资源引用与构建。
2. **部分成功状态**：设计并实现可靠的 `partially_completed` 链路。讲解或题目能否交付，必须经过相应证据、审核、授权和持久化验证；覆盖 SSE、刷新／断线恢复、教师审核、拒绝和跨用户课程隔离。不要将未审核内容标为已验证。目前整体失败时保持关闭式处理，尚未实现此功能。
3. **结构化输出稳定性与评测**：分析开发集失败原因，在新的独立任务上验证；保持原实验不变，按失败、调用数、延迟和可得用量如实汇总。付费调用已有授权，但不要虚构账单或评审。
4. **真实人工评审**：两位独立人员完成留出集盲评与逐 claim 审查，必要时第三人裁决；程序不证明人的身份或评分独立性。原始资料只留本地，公开汇总须脱敏核验。
5. **CI 与环境**：生成、安装并验证 Linux Python 3.12 锁文件；按用户不自行下载依赖的要求协调安装；检查 GitHub Actions 在实际提交后的结果，并运行 PostgreSQL/Redis 真实集成与迁移。Docker 引擎未运行或镜像不存在时，不自行拉取镜像。
6. **安全和交付**：继续核对 V1 生产权限边界、第三方素材许可、生产口令与密钥；补真实演示、Release 和部署材料。不要将占位口令或模型密钥混入发布物。

## 8. 密钥检查与操作边界

本地曾以 `output/private-secret-check.py` 将 Git 候选文件与原项目 `.env` 中匹配到的若干私有值进行对照，未发现模型 API 密钥匹配；仅报告已有占位口令匹配。这是**有限检查，不是完整安全审计**，也不覆盖所有历史提交或所有可能来源的密钥。正式发布前应重新检查将被提交的完整文件和历史，检查结果只输出文件路径或安全摘要，不打印密钥。

`output/`、运行时 `data/artifacts/`、`data/benchmarks/`、`data/rag/`、教师上传等被 `.gitignore` 排除；已跟踪文件仍可能例外，必须实际核对。不得把原始模型响应、课程证据、用户数据或真实凭据加入提交。任何清理、重建、重置、推送或发布前先确认实际目标和影响。
