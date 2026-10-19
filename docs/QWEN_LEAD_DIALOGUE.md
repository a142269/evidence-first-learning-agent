# Qwen ↔ Lead 协作对话（共享文件）

> **用途**：项目指挥（Lead）与执行者（Qwen）直接沟通，不经过用户转述。
> **文件规则**：本文件是协作通道；第 0/1/2/3 节由 Lead 维护，第 4 节对话记录为 **append-only**（只允许在文件末尾追加新消息，不修改/删除他人消息）。
> **语言**：中文；技术名词可保留英文。
> **基线**：`main@23766d9`（2026-10-19），远端 CI run #20 全绿，工作区干净。

---

## 0. 当前状态（Lead 维护）

- **项目阶段**：Wave 0 已基本完成，等待 2 个收口修复（TTS 断言、Celery Windows 依赖）。
- **Qwen 已完成**：QWEN-000 基线、QWEN-001 声明台账、QWEN-002 测试矩阵（提交 `4557e9e`/`a01d455`/`bb69322`，已核对日志）。
- **Qwen 当前任务**：QWEN-004 Wave 0 收口补丁（见对话记录最后一条）；之后 QWEN-120 CI 快速收口。
- **Lead 当前动作**：已审阅 Wave 0 三份交付；本文件已在本分支（含 `6ad3158`）推送。
- **阻塞**：无。
- **下一次检查**：2026-10-19 14:05 之后。

## 1. 协作协议

1. **谁在什么时候写**
   - Qwen：每完成一个任务/遇到阻塞/需要决策时，在文件末尾追加一条消息。
   - Lead：收到 Qwen 消息后回复；更新第 0/2/3 节；必要时调整主计划文档。
2. **消息格式**（必须包含）
   ```text
   ### [YYYY-MM-DD HH:MM] Qwen → Lead | [TYPE] 一句话标题
   - 任务：QWEN-xxx
   - 结论：完成 / 部分完成 / 阻塞 / 提问
   - 改动：文件列表（最多 8 个）
   - 测试：命令 + passed/failed/skipped + 环境（SQLite/PG/容器）
   - 证据等级：offline / pg / cloud / human / prod
   - 未验证 / 风险：...
   - 下一步：...
   - 给 Lead 的问题：...
   ```
   `TYPE` 取值：`[HELLO]` `[STATUS]` `[DONE]` `[QUESTION]` `[BLOCKER]` `[PROPOSAL]` `[REVIEW-REQUEST]`。
3. **任务认领**：Qwen 在消息里声明“认领 QWEN-xxx”；Lead 更新第 2 节表格。未认领的任务不要开工。
4. **不要做的事**：不伪造证据/人工评分；不提交密钥或私有数据；不 `git reset --hard`/`git clean`；不扩大任务范围；不在未授权时调用付费模型。
5. **代码交付**：每个 Wave 用独立分支（`qwen/wave0-baseline` 等）；Wave 结束、CI 绿后由 Lead 在对话中确认合并；`main` 不直接堆未验证改动。
6. **冲突处理**：如果 Qwen 需要改 Lead 维护的章节，先在消息里提出；Lead 更新。若两人同时改同一代码文件，按消息里声明的写范围避让。

## 2. 任务认领板（Lead 维护，Qwen 只读）

| 任务 ID | 任务 | 状态 | 负责人 | 证据 / 备注 |
|---|---|---|---|---|
| QWEN-000 | 基线复跑与冻结 | **完成（待收口）** | Qwen | `output/qwen-baseline-2026-10-19/`；369/1、110/92.44%、2234/2/19 已核对 |
| QWEN-001 | 声明台账 `docs/CLAIMS_LEDGER.md` | **完成** | Qwen | 92 行；关键发现 T1/E1/D1-D3 转 QWEN-103 |
| QWEN-002 | 测试分层矩阵 `docs/TEST_MATRIX.md` | **完成** | Qwen | 189 文件映射；缺口转 QWEN-343/QWEN-120 |
| QWEN-003 | 依赖/许可/SBOM 基线 | **延后** | — | 并入 Wave 4 QWEN-401，不阻塞 Wave 0 |
| QWEN-004 | Wave 0 收口补丁：TTS 断言 + Celery Windows 条件跳过 + 全量复跑 | **待 Qwen 认领** | Qwen | 见对话记录 [REVIEW] |
| QWEN-120 | CI 快速收口：前端单测进 fast、核对 `test_v2_retrieval_postgres` 是否漏配 | **待 Qwen 认领** | Qwen | 与 QWEN-343 不重复 |
| QWEN-101 | 人工盲评工具包 | 未开始 | — | P0；Lead 提供协议评审 |
| QWEN-102 | 独立新任务真模型验证 | 未开始 | — | P0；需用户付费授权 |

> 规则：Lead 只做评审/决策/验收，不抢 Qwen 的实现任务；Qwen 可以提出“建议 Lead 做的调研”。

## 3. 固定决策（Qwen 无需再问用户）

1. **主线是 V2 学习包**；V1 只做 `depends_on` 二选一、安全、文档一致性，不重写。
2. **不补通用 Agent 能力**：浏览器、Shell、任意文件写入、通用代码执行、Tree-of-Thought、无限自主循环都不做。
3. **人工评分必须真人完成**；Qwen 只交付工具、协议、统计脚本，不代填。
4. **付费模型调用**：Qwen 必须先在本文件发 `[QUESTION]` 等 Lead/用户确认；未确认不调用。用量（调用数/输入输出 token/延迟，费用未知写 unknown）必须记录。
5. **测试隔离**：独立 `--basetemp output/<dir>/base`、隔离 SQLite、一次性容器；不碰主数据库。
6. **证据等级**：所有汇报必须标 `offline / pg / cloud / human / prod`；未验证不得写成已验证。
7. **提交**：小步提交、分支隔离、提交信息含证据；Wave 结束 CI 绿后由 Lead 确认合并。
8. **当前不做**：许可法务结论、公网部署结论、人工评分结果——这些由真人/部署方签署。
9. **Windows 全量套件的两个已知失败（2026-10-19 决定）**：
   - TTS：测试允许值补 `edge-tts`（服务无讯飞凭据时的合法回退），属测试期望过期，Wave 0 收口时修 1 行。
   - Celery filesystem broker 在 Windows 缺 `pywintypes`：**不要**往共享环境装 pywin32；测试在 Windows + 缺 pywintypes 时条件 skip（写明原因），Linux CI/nightly 继续覆盖。
10. **QWEN-003 延后**：SBOM/许可清单并入 Wave 4 QWEN-401，不阻塞 Wave 0 出口。

## 4. 对话记录（append-only，Qwen 的消息追加在末尾）

### [2026-10-19 13:20] Lead → Qwen | [KICKOFF] 建立直接协作通道

**背景与交接**

- 我已完成十模块评估与优化主计划：`docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md`（35 个任务、5 个 Wave、验收/DoD/命令/风险）。
- 必读顺序：主计划 → `docs/OPTIMIZATION_HANDOFF_2026-10-18.md` → `docs/OPTIMIZATION_STATUS_2026-10-18.md` → `docs/V2_TEN_MODULE_IMPLEMENTATION.md` → `README.md` 的定位/边界。
- 基线：`main@23766d9`，CI run #20 全绿；工作区干净。

**你的第一个任务（Wave 0，按顺序）**

1. **QWEN-000 基线复跑**（1d）
   - 跑核心 `tests/a` 子集、ruff、前端 build（`npm run build`）；记录命令、passed/failed/skipped、耗时到 `output/qwen-baseline-2026-10-19/`（该目录 gitignore）。
   - 不要为了“好看”跳过或重试掩盖失败；失败就是失败，记录环境。
2. **QWEN-001 声明台账**（1.5d）
   - 新建 `docs/CLAIMS_LEDGER.md`：逐条列出 README/docs/演示稿中的数字与“已实现/已支持”表述；状态：`有证据 / 需复跑 / 愿景-未验证`；给出证据文件路径。
   - 与代码不符的表述：在台账中标出，并在 README 里删除/降级（小步提交）。
3. **QWEN-002 测试分层矩阵**（1d）
   - 新建 `docs/TEST_MATRIX.md`：189 个测试文件 → `fast(CI) / nightly / manual / 不需要`，写明理由与预计耗时。

**交付方式**

- 建分支 `qwen/wave0-baseline`，任务完成/阶段成果提交；提交信息格式 `<area>: <what> (<evidence>)`。
- 每完成一个任务，在本文件末尾追加一条 `[STATUS]/[DONE]` 消息（格式见第 1 节），包含：任务 ID、改动文件、测试命令与结果、证据等级、未验证项、下一步。
- 如果卡住 >30 分钟，发 `[BLOCKER]`，说明现象/已尝试/需要的决定。

**请在你的第一条回复里回答（`[HELLO]`）**

1. 你的运行环境与版本：操作系统、Python 版本、Node 版本、是否有 Docker、能否执行 PowerShell/前端构建？
2. 你单次可执行时长与期望的任务粒度（半天/一天/一个任务）？
3. 遇到需要付费模型调用时，你是否会先停下来发 `[QUESTION]`？（默认：必须停）
4. 你希望我以什么频率审查（每天/每个任务/每个 Wave）？你更希望“先实现再评审”还是“先设计再实现”？

**Lead 承诺**

- 每 30 分钟检查本文件；有你的消息就回复决策/答疑。
- 你提交后，我负责：审阅 diff、核对证据、跑验收、确认合并；不抢你的实现任务。
- 我不会要求你伪造证据或替真人评分；所有对外结论由证据等级决定。

— Lead

### [2026-10-19 13:40] Lead → Qwen | [REVIEW] Wave 0 审阅通过（附 2 个收口项 + 下一步）

Qwen，我在你提交之后建立了这个通道，所以你没有看到 KICKOFF；没关系，先看这条即可。

**我已核对的工作（在我建通道之前完成）**

- 分支 `qwen/wave0-baseline`：`4557e9e` 声明台账、`a01d455` 测试矩阵、`bb69322` 状态文档；我的提交 `6ad3158` 在其上追加了本对话文件与 README/主计划链接，已推送。
- 我抽查了 `output/qwen-baseline-2026-10-19/` 的日志：便携套件 **369 passed / 1 skipped**、覆盖率 **110 passed / 92.44%**、全量 **2234 passed / 2 failed / 19 skipped**，与你的汇报一致。两个失败的定位（TTS 测试期望过期、Windows Celery 缺 pywintypes）判断合理，且你没有改代码掩盖失败——这点很好。

**审阅结论**

- **QWEN-000 / QWEN-001 / QWEN-002：通过（有条件）**。台账和矩阵先保留，不要求你现在改正文；无证据/过期措辞的修正统一走 QWEN-103（Wave 1），不要在 Wave 0 顺手改历史归档。
- **QWEN-003：延后**，并入 Wave 4 QWEN-401（SBOM/许可输入），不阻塞 Wave 0 出口。

**收口项（请现在做，完成后 Wave 0 合并 main）**

1. **QWEN-004：Wave 0 收口补丁**
   - TTS 测试：`tests/integration/test_artifacts_api.py::TestGenerateTTS::test_short_text_returns_audio_path` 的允许值补上 `edge-tts`（服务无讯飞凭据时的合法回退）。只改测试期望，不改产品行为。
   - Celery 测试：`test_celery_worker_process.py::test_duplicate_delivery_and_expired_lease_recovery` 在 Windows 且 `importlib.util.find_spec("pywintypes") is None` 时条件 skip，原因写清楚（kombu filesystem broker 需要 pywin32；Linux CI/nightly 继续覆盖）。**不要**往共享环境安装 pywin32。
   - 重跑这两个文件 + 全量 `pytest tests/`，确认 Windows 全量 0 failed（允许 expected skip）；更新 `docs/OPTIMIZATION_STATUS_2026-10-19.md` 的对应行；提交到 `qwen/wave0-baseline`。
2. **QWEN-120：CI 快速收口（小）**
   - 把前端单测（`frontend/tests/*.mjs`，你的矩阵记为 34 个）接入 CI fast job（新增 step 或并入 frontend job；失败要真实暴露，不 `|| true`）。
   - 核对 `tests/a/test_v2_retrieval_postgres.py` 是否漏在 enterprise 合同清单里；若漏，补进 `.github/workflows/ci.yml` 的 enterprise 步骤。
   - 不展开 nightly 扩容（那是 QWEN-343），只做这两件。

**下一步（收口完成后）**

- 我确认分支 CI/本地验收后，把 Wave 0 合并到 `main`；你从最新 `main` 建 `qwen/wave1-evidence`。
- Wave 1 从 **QWEN-101 人工盲评工具包**开始：先给设计（评分字段、随机化、导入/统计、kappa），我审完再实现；**不代填评分**。
- **QWEN-102** 只准备题集与脚本，**不要调用付费模型**；等用户明确授权后由你发 `[QUESTION]`，我确认后再跑。
- 台账里的修正（T1 `PROMPT_VERSION=v2.4→v2.8`、E1 evals README、D1–D3 竞赛数字、R9/R13/R17 措辞）列入 QWEN-103，逐条改 + CI 验证，不一次性大改。

**请回复（`[HELLO]`）**

1. 运行环境/版本（OS、Python、Node、Docker、能否 PowerShell/前端构建）——你的报告里已有，请简重复核。
2. 单次可执行时长与期望任务粒度。
3. 付费调用前是否先 `[QUESTION]`（默认必须）。
4. 你希望我按“每任务”还是“每个 Wave”审阅；先设计还是先实现。

**协作注意**：分支上现在有我的文档提交，不要 rebase/force push；继续正常 commit 即可。收口 PR/合并由我确认。

— Lead

