# Qwen ↔ Lead 协作对话（共享文件）

> **用途**：项目指挥（Lead）与执行者（Qwen）直接沟通，不经过用户转述。
> **文件规则**：本文件是协作通道；第 0/1/2/3 节由 Lead 维护，第 4 节对话记录为 **append-only**（只允许在文件末尾追加新消息，不修改/删除他人消息）。
> **语言**：中文；技术名词可保留英文。
> **基线**：`main@23766d9`（2026-10-19），远端 CI run #20 全绿，工作区干净。

---

## 0. 当前状态（Lead 维护）

- **项目阶段**：十模块评估完成，进入 Wave 0（基线与治理）。
- **Qwen 当前任务**：等待认领 QWEN-000 / QWEN-001 / QWEN-002。
- **Lead 当前动作**：已建立本通道；每 30 分钟检查一次，有新消息即回复。
- **阻塞**：无。
- **下一次检查**：2026-10-19 13:45（Asia/Shanghai）之后。

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
| QWEN-000 | 基线复跑与冻结 | 待认领 | — | 目标：真实 passed/failed/skipped + 耗时 |
| QWEN-001 | 声明台账 `docs/CLAIMS_LEDGER.md` | 待认领 | — | 覆盖 README/docs 全部对外数字 |
| QWEN-002 | 测试分层矩阵 `docs/TEST_MATRIX.md` | 待认领 | — | 189 个测试文件 → fast/nightly/manual |
| QWEN-003 | 依赖/许可/SBOM 基线 | 待认领 | — | 只做清单，不做法务结论 |
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
