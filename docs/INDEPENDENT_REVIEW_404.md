# QWEN-404 独立复核执行指南（未完成，待外部复核者）

> 状态：**未完成（P0）**。本文件是交接包，不是复核报告。
> 在独立复核者提交 PASS 报告前，发布只能称 `v1.0.0-rc1` 候选，不得称 GA/已上线/验收通过。
> 本文件由 Lead 维护；复核者只追加自己的报告，不改本文件正文。

## 1. 什么叫“独立”

满足全部条件才算：

1. 未参与本仓库开发、未提交过本仓库代码、未参与本次优化对话；
2. 使用**全新上下文/只读克隆**，不依赖 Lead/Qwen/Trae 的口头结论；
3. 不读取、不打印、不提交 `.env`/密钥；不访问生产环境；
4. 不调用付费模型；默认 `A3_OFFLINE_DEMO=true`、`LLM_PROVIDER=none`；
5. 只读仓库；如需修复问题，另开分支/PR，不在复核分支上顺手改产品。

不满足以上任一条，只能算“自查”，不能关闭 404。

## 2. 复核对象

- 起点提交：`7f7531f`（或复核者记录的实际 `main` tip；以 `git rev-parse HEAD` 为准）
- 必读文档：
  - `README.md`（测试/CI 行）
  - `docs/CLAIMS_LEDGER.md`（重点 §27–§45）
  - `docs/TEST_MATRIX.md`
  - `docs/RELEASE_DRAFT.md`（含 Known limitations）
  - `docs/DIST_NOTICE_DRAFT.md`、`docs/RELEASE_LICENSE_REVIEW.md`
  - `docs/PRODUCTION_RUNBOOK.md`
- 预期基线（供对照，不是让复核者照抄）：
  - 全量 `pytest tests/`：**2520 passed / 0 failed / 20 skipped**（Windows + Python 3.12.15，约 20–25 分钟；Linux/不同环境可能有时长与条件 skip 差异）
  - CI 快清单：**54 文件 / 649 passed / 1 skipped**
  - `PROMPT_VERSION = learning-package-v2.9`
  - 发布口径：**只能是 `v1.0.0-rc1` 候选**

## 3. 环境准备（只读克隆）

```bash
git clone <repo-url> review-404
cd review-404
git checkout 7f7531f        # 或复核时的 main tip
git status --short --branch # 期望干净
test ! -f .env && echo "no .env (good)"
```

Python 3.12 虚拟环境示例（Windows PowerShell / Linux 均可）：

```powershell
python -m venv .venv-review
.venv-review\Scripts\Activate.ps1
pip install -r requirements.txt
$env:A3_OFFLINE_DEMO="true"
$env:LLM_PROVIDER="none"
$env:DATABASE_URL="sqlite:///./output/independent-review/db.sqlite"
New-Item -ItemType Directory -Force output/independent-review | Out-Null
python -c "from backend.app.core.database import init_db; init_db()"
```

Linux 用 `source .venv-review/bin/activate`、`mkdir -p output/independent-review`。

**不要**使用仓库根 `.env`，不要连生产库，不要起容器/公网服务。

## 4. 必跑命令（记录原始输出）

### 4.1 关键定向套件（先快后慢）

```bash
python -m pytest \
  tests/a/test_learning_package.py \
  tests/a/test_learning_package_partial.py \
  tests/a/test_claim_support.py \
  tests/a/test_observation_claim_support.py \
  tests/a/test_user_memory_service.py \
  tests/a/test_user_memory_migration.py \
  tests/a/test_session_summary.py \
  tests/a/test_tool_registry_permissions.py \
  tests/a/test_permission_matrix.py \
  tests/a/test_run_queue.py \
  tests/a/test_prompt_registry.py \
  tests/a/test_prompt_injection_redteam.py \
  tests/a/test_quota.py \
  tests/a/test_run_metrics.py \
  tests/a/test_run_usage_admin.py \
  --basetemp output/independent-review/base \
  -o addopts= --benchmark-disable -q
```

期望：与文档中对应卡片数字一致；若不同，记录**实际数字 + 环境**，不要改文档去迎合。

### 4.2 全量

```bash
python -m pytest tests/ \
  --basetemp output/independent-review/full-base \
  -o addopts= --benchmark-disable -q
```

期望基线：**2520 passed / 0 failed / 20 skipped**。时间较长（20–25 分钟），建议放后台并记录 `PYTEST_EXIT`。

### 4.3 CI 快清单

从 `.github/workflows/ci.yml` 的 `Pytest (portable V2 contract suite)` 步骤机械提取 54 个文件（不要手抄），用同形旗标：

```bash
python -m pytest <54 files> \
  --basetemp output/independent-review/ci-base \
  -o addopts= --no-cov --benchmark-disable -q -rs
```

期望：**649 passed / 1 skipped**；唯一 skip 应为 `test_auth_restart.py:18`（要求一次性 PostgreSQL）。若 skip 数不同，记录原因。

### 4.4 静态门

```bash
ruff check --select=F821,F823,E9 backend/app scripts/ tests/
git diff --check
```

期望：ruff `All checks passed`；diff check 干净（CRLF 提示不算失败）。

## 5. 文档与行为抽查（不能只看测试绿）

逐项核对并记录证据：

1. **Memory 门控**：`user_memory.propose` 不落库；`confirm` 需 `student/teacher`；partial/failed 七态拒入；`active` 唯一。
2. **跨会话摘要**：只读 active 未过期；`persisted=False`；不写回 `user_memories`；空态两种 reason。
3. **ToolRegistry**：9 工具×5 角色；未知/越权/非法参数拒绝且执行面零调用；每结局一条审计。
4. **权限矩阵**：10 条 V2 路由全声明；CI 枚举硬门；未声明路由失败；既有授权行为不变。
5. **Run 队列**：`/enqueue` 返回可查询 ID；租约/心跳/取消/超时；崩溃重领；**不声称 exactly-once**。
6. **Claim-support**：失败 fail-closed，不交付/返工；引用不足错误码稳定。
7. **Prompt 注册表**：字节不变、hash 校验、回退 warning；`verify_registry()` CI 硬门。
8. **红队**：25 项四类面；不越权/不泄露；guard 修复（NFKC/Cf/无视）不被绕过。
9. **配额/指标**：429 + Retry-After；`QUOTA_ENABLED=true` 生产启用；`/metrics` 401/403/200；成本 unknown 不当 0。
10. **发布诚实性**：无“已合规/已签署/已上线/GA/remote nightly 已绿”等未验证表述；404/法务/视频/截图/公网项明确待办。

## 6. 差异分级与结论

- **P0**：证据与文档结论矛盾、测试失败、安全/权限绕过、release 口径虚假 → **FAIL/BLOCKED**，必须修复并复跑。
- **P1**：数字/环境/命令不一致但不改变结论 → 记录，要求文档修正。
- **P2**：措辞、可维护性建议 → 记录，不阻塞。

**只有全部 P0 关闭、且复核者独立确认“文档结论可复现”，404 才能 PASS。**

## 7. 复核报告模板

复核者在 `docs/independent-review/REPORT.md`（新目录，只放报告与聚合结果，不放密钥/原始日志）填写：

```markdown
# Independent Review Report — QWEN-404

- Reviewer: <name/handle>（人类/独立 Agent）
- Independence attestation: 未参与开发；未使用此前对话上下文；只读克隆
- Date:
- Commit: <git rev-parse HEAD>
- Environment: OS / Python / pytest / DB / offline flags
- Commands run: <逐条>
- Results: full=<a/b/c>; CI=<x/y>; targeted=<...>
- Discrepancies: P0=<n>; P1=<n>; P2=<n>（逐条列文件/命令/证据）
- Unverified: <remote nightly / PG / 公网 / 法务 / 视频等>
- Verdict: PASS / FAIL / BLOCKED
- Signature: <name + date>（AI 复核者写模型名与运行时间，不能冒充人类签署）
```

日志放 `output/independent-review/`（gitignored）；报告中只写聚合数字、命令、差异，不贴 prompt/密钥/个人数据。

## 8. 常见坑

1. Windows 本机 `.env` 会影响部分测试（如 `EMBEDDING_BATCH_SIZE`）；复核不要用仓库 `.env`，用独立环境变量。
2. 全量在负载下 `test_demo_journey` 可能贴 30s 墙钟抖动；单跑复验，记录是否环境问题，不要直接判产品失败。
3. nightly 的 remote 回执未验证；本地跑夜间批不等于 GitHub nightly 绿。
4. 本地全量 2520/0/20 是 Windows 口径；Linux 条件 skip/时长可能不同，如实记录。
5. 不要用 `git clean`/`reset --hard`，不要改产品代码“让它绿”；修复另开 PR。
6. 不要用 `result.evidence` 判断“不泄露检索内容”——该字段是既有审计设计，泄露边界以交付正文/引用/模型输入为准（见台账 §39.2）。

## 9. 给独立 AI Agent 的交接提示

若复核者是另一个 AI Agent，需新开会话、不带此前对话上下文，并把本文件作为唯一流程依据；提示词：

```text
你是独立复核 Agent，未参与本仓库开发。请只读完成 QWEN-404：
- 读 docs/INDEPENDENT_REVIEW_404.md，按其步骤在只读克隆上复跑；
- 不读 .env/密钥，不调用付费模型，不改产品代码；
- 记录真实命令/输出/差异，按第 7 节模板写 docs/independent-review/REPORT.md；
- 给出 PASS/FAIL/BLOCKED 与 P0/P1/P2；不得用“看起来通过”代替证据；
- 若发现 P0，只报告并给最小修复建议，不在复核分支直接改。
```

## 10. 关闭 404 的判据

- 独立复核报告 `Verdict: PASS`；
- 无未关闭 P0；
- 报告中的 commit 与发布 commit 一致；
- 法务/视频/截图/公网项仍可未完成，但必须在 release 声明中保留“未验证/待人工”，不能因此宣称 GA。
