# 声明台账（Claims Ledger）

> 编写：Qwen（本项目唯一主执行者）· 日期：2026-10-19 · 分支：`qwen/wave0-baseline` · 核对基线：`main@23766d9`
> 任务：QWEN-001（Wave 0）。依据 [Qwen 优化主计划](QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md) §6 Wave 0。
> 方法：逐条核对 README、对外评测材料、演示/评审文档与第三方清单中的**每个对外数字**和**"已实现/已验证"措辞**，
> 与当前代码、自动化测试、`evals/results/` 公开汇总和 `docs/OPTIMIZATION_STATUS_*` 归档记录比对。
> 本台账只登记核对结论；对过期或不准确表述的**修正动作**列入"建议动作"，由后续 Wave 执行（历史归档文档不回改正文，只在此处标注）。

## 图例

状态：

- `有证据` —— 当前代码 + 可复跑测试或已发表脱敏汇总支持，措辞与证据一致。
- `有证据-历史` —— 数字真实产生于过去某日的运行，文档已（或应在）明示"历史，非当前提交自动重跑"。
- `需复跑` —— 本次 Wave 0 未重跑，需在后续 Wave（PG 容器 / nightly / 远端 CI）复跑确认。
- `措辞需修正` —— 与当前代码/事实不符或易被误读，需要降级、加注或改数。
- `愿景/自评` —— 规划、竞赛自评或学术性主张，不作为工程事实宣称。
- `待人工` —— 必须由真人完成（人工盲评、素材法务、浏览器走查、远端页面复核）。

证据等级（与主计划 §1.3 一致）：`offline`（SQLite/内存检查点/可控模型）、`pg`（真实 PostgreSQL/Redis 隔离容器）、`cloud`（真实模型调用）、`human`（真人评分/审核）、`prod`（目标部署环境；当前仅=本机生产栈，非公网）。

---

## 1. README.md（仓库门面，最高对外权重）

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| R1 | L13 CI badge | main 分支 CI 绿 | 需复跑（远端） | —（CI 环境） | GitHub Actions 徽章是实时远端状态；本机无 `gh` CLI，本轮未能程序化复核。归档记录：2026-10-18 run #17/#18 全绿，主计划基线注记 run #19 全绿（`1ba64fa`）；Wave 0 合并（merge `5bf77d1`）后 **run #21 success**（Lead 2026-10-19 14:55 报告，含 node 20 前端单测 step；证据等级 `remote`，非本机复核）。 | Wave 1 起每次合并后在状态文档记录 run 编号与结论；如要本机复核需给 `gh` CLI 或网络权限 |
| R2 | L25 | "每个回答都携带实际使用的来源" | 有证据 | offline | `tests/a/test_learning_package.py` 覆盖未使用证据排除、逐项引用、按 chunk_id 去重；今日便携套件重跑通过。 | 保持 |
| R3 | L25 | "PostgreSQL 检查点和执行租约实现断线恢复" | 有证据 | offline + pg | 检查点跨进程恢复、租约、API 崩溃恢复测试在 CI enterprise 与 2026-10-18 一次性容器（353 passed）验证；今日 SQLite 便携子集复跑通过。 | 保持；PG 组合本轮未重跑（QWEN-105） |
| R4 | L27 | V2 旗舰链路（受限规划→Tutor→Practice→Reviewer→一次返工→按需人审） | 有证据 | offline（契约）+ cloud（单次采集） | 代码 `learning_package.py`（v2.8）+ 便携套件今日 369 passed；真实后端 13 条标准场景采集通过（cloud 历史）。契约测试不等于内容质量。 | 保持 |
| R5 | L29 | "`depends_on` 是未执行的兼容字段，不提供 DAG 依赖调度" | 有证据 | offline | 与 `orchestrator.py` 实现一致；README 主动降级表述，正确示范。 | V1 `depends_on` 二选一处置属 QWEN-212 |
| R6 | L31 | "三组对照已记录 72 次真实模型运行"；"双人质量复核尚未完成" | 有证据 | cloud + 待人工 | `evals/results/ablation-fixed-evidence-20261017.md`：24 任务 × 3 组 = 72 次，真实 DeepSeek Flash；人工评分确实未完成，措辞诚实。 | 保持（这是正确的"不宣称"范例） |
| R7 | L39 | "76 条新版 Golden Set 中 74 条通过" | 有证据-历史 | cloud | 2026-10-16 第二轮在线验收（`UPGRADE_IMPLEMENTATION_STATUS.md` 最终批）；脱敏汇总 `evals/results/qa-golden-v2-summary.json`（74/76、pass_rate 0.9737）。逐例原始记录只在本地 `output/`，未上传。 | 保持，但建议加"2026-10-16 历史"角标（L48 已有总说明） |
| R8 | L40 | "真实 PostgreSQL 恢复组合 15/15" | 有证据-历史 | pg | 2026-10-16 PG 专项（检查点跨进程、API 崩溃恢复、摄取幂等、向量版本检索、续跑）15/15；10-18 又跑 353 passed 企业组合。本轮未重跑。 | 需复跑 → QWEN-105 一次性容器复跑 |
| R9 | L41 | "13 个在线契约场景 13/13" | 有证据-历史 + 措辞需修正 | cloud（采集）→ offline_replay（评测） | `evals/results/learning-package-v1-summary.json`：`evaluation_mode=offline_replay`、`prediction_kind=recorded`；13/13 指**契约**（结构/引用/预算），且 `human_review_coverage=0.0`。"在线契约"字样易被读成在线质量。 | 措辞改为"真实后端采集的 13 条契约场景（回放评测；非内容质量）" |
| R10 | L52–55 | 74/76（97.37%）、Hit@5 95.83%、Recall@5 94.79%、引用 100%/100% | 有证据-历史 | cloud | 与脱敏汇总 JSON 逐项一致（0.9583/0.9479/1.0/1.0）。README L62 已声明为历史汇总；引用"有效率"= ID 存在性（L31 已自声明非事实支持）。 | 保持 |
| R11 | L56 | "本地离线测试 2153 passed, 18 skipped" | 有证据-历史；本轮已复跑并收口 | offline | 原值：2026-10-16 Windows **Python 3.10** 全量 `pytest tests/`（626 s）。本轮 2026-10-19 在 Python 3.12.15（conda `evidence-agent-py312`）复跑全量：首轮 **2234 passed / 2 failed / 19 skipped（650.31 s）**；两处失败定位为① Windows kombu filesystem broker 缺 pywin32、② TTS 回退 `edge-tts` 未列入测试允许值，均属环境/测试期望而非 V2 主线回归。QWEN-004 收口（只改测试：补 `edge-tts` 允许值 + Windows 缺 `pywintypes` 条件 skip）后复跑 **2235 passed / 0 failed / 20 skipped（612.61 s）**。明细见 `output/qwen-baseline-2026-10-19/`（本地，Git 忽略）。 | README 更新为最新复跑口径（2235/0/20，py3.12.15 Windows）并加"运行环境（py 版本/平台）"注记；措辞修正动作归 Wave 1 QWEN-103 |
| R12 | L57 | PostgreSQL 专项 15/15 | 有证据-历史 | pg | 同 R8。 | 同 R8 |
| R13 | L58 | 学习包标准在线契约 13/13 | 有证据-历史 | cloud→offline_replay | 同 R9。 | 同 R9 |
| R14 | L42 | 生产权限边界 "SQLite / PostgreSQL 跨进程验证" | 有证据 | offline + pg | V1 白名单、V2 逐 Run 授权、跨进程认证测试在便携套件今日重跑通过；PG 跨进程认证为历史 pg 证据。 | 保持 |
| R15 | L43 | 摄取"幂等、重投和租约接管测试" | 有证据 | offline + pg | `test_v2_ingestion_idempotency.py`、`test_celery_worker_process.py`（文件队列/Redis broker 双模式）；不承诺 broker 自动重投/exactly-once（文档已声明）。 | 保持 |
| R16 | L44 | "可重放评测与用量审计" | 有证据 | offline | 评测报告含数据集签名/evaluator_version；`test_v2_model_usage.py` 今日重跑通过。 | 保持 |
| R17 | L8 tagline | "企业级、可追溯、可恢复" | 措辞需修正（边界注记） | prod=仅本机 | 本机生产 Compose 全栈构建/启动 + 边界验收通过（10-18 第六批）；**公网 TLS/域名/备份/监控未验证**。"企业级"若无此注记易被读成已公网生产。 | 在 README 或 PRODUCTION_DEPLOYMENT 链接处加一句"公网生产部署未验证" |
| R18 | L91 | 部分完成状态链（六状态、分项交付） | 有证据 | offline + pg | `test_learning_package_partial.py` 今日 22 项重跑通过；`test_learning_package_partial_postgres.py` 历史 pg 1 passed。 | 保持 |
| R19 | L97–98 截图 | 产品界面截图 | 待人工 | human | 截图与当前 UI 是否一致未核验（主计划 P2 已知项）。 | Wave 4（QWEN-402）重截 |
| R20 | L134 | "Linux 锁 144 个包、带哈希"；nightly `linux-lockfile` 安装并跑核心测试 | 有证据（本地）+ 需复跑（远端） | offline（Linux 容器历史 66 passed）+ CI 环境 | 本轮实测 `requirements.lock.linux.txt` 包数 = 144 ✓；nightly 工作流已定义该 job，但**远端 nightly 实际运行记录未核验**（计划注记"nightly 未手动跑"）。 | 触发一次远端 nightly 并把 run 编号记入状态文档 |
| R21 | L144 | 演示账号 `demo-student-1`/`123456` | 有证据 | offline | 仅离线预览/开发模式；生产模式内置演示账号被 `deployment_policy` 禁用并有测试。 | 保持（所在章节已限定"离线预览"） |
| R22 | L170 | 验证建议 `pytest tests/` | 有证据-历史 | offline | 全量套件确可本地运行；但 fast CI 只跑便携子集，全量在 nightly。两者关系见 [TEST_MATRIX.md](TEST_MATRIX.md)。 | README 验证节可加一句"全量约 X 分钟，CI 分层见 TEST_MATRIX" |
| R23 | L219 | MIT 许可证 | 有证据 | — | `LICENSE` 已跟踪，MIT 文本、版权行"2026 智学领航 contributors"。 | 保持；第三方素材许可仍是待人工项（§6） |

## 2. evals/（评测对外材料）

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| E1 | evals/README.md L1–3 | "76 条集……目前未完成真实云端验收" | 措辞需修正（过期） | cloud | 文首日期 2026-10-12；实际 2026-10-16 已完成两轮 76 条在线验收（第二轮 74/76 全门槛通过）。仍**未完成**的是：学习包 24 条完整在线质量评测、逐 claim 人工审查。 | 加"截至 2026-10-12"横幅或更新该句；归 QWEN-103 |
| E2 | evals/README.md L7 | 76 = 48 事实 + 18 拒答 + 10 人审 | 有证据 | offline（数据文件） | 本轮按 `category` 字段统计：course_qa 44 + cross_chapter 4 = 48；unsupported_write 10 + no_answer 3 + prompt_injection 3 + permission_isolation 2 = 18；content_review 10。✓ | 保持 |
| E3 | ablation-fixed-evidence-20261017.md | 72 次运行；23/24、13/24、13/24；留出 26/36 | 有证据 | cloud | 单次运行、冻结证据、v2.5、费用未知、"完成"仅结构契约——局限均已写明；机器汇总 JSON 已发表。 | 保持（正确示范） |
| E4 | retry-development-20261017.md | v2.5 6/12 → v2.6 9/12 | 有证据 | cloud | 已自我声明"探索性、各跑一次、不能归因"。 | 保持 |
| E5 | structured-output-20261018.md | v2.8 dev 12/12、holdout 12/12；44/43 次调用；输出 25,384/25,286 tokens；费用未知；6 次截断均重试恢复 | 有证据 | cloud | 局限（单次、捆绑改动、留出集非全新、不证质量）已写明；费用未写 0 ✓。 | 保持；"新独立任务真模型验证"仍属 QWEN-102（需付费授权） |
| E6 | qa-golden-v2-summary.json / learning-package-v1-summary.json | 脱敏汇总 | 有证据 | cloud（转录） | 与 README 数字逐项一致；`limitations` 字段诚实（逐例原始记录未公开、契约≠质量、人审 0%）。 | 保持 |
| E7 | 双人盲评/裁决工具（scripts/prepare_ablation_*） | "已实现工具，评分待真人" | 有证据（工具）+ 待人工（评分） | offline / human | 工具测试 `test_ablation_review_packets.py` 今日重跑通过；无任何文档宣称评分已完成。 | 评分执行需真人 2 名（QWEN-101 交付工具与协议） |

## 3. docs/V2_TEN_MODULE_IMPLEMENTATION.md（自称"描述当前代码"）

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| T1 | §8 L58 | "`PROMPT_VERSION=learning-package-v2.4`" | 措辞需修正（过期） | offline | 代码当前为 **v2.8**（`learning_package.py:20`）；`WORKFLOW_VERSION=learning-workflows-v2.3`（`run_lifecycle.py:29`）。文档头部日期 2026-10-15 未随后续批次更新。 | QWEN-103：全文按当前代码刷新版本号与批次差异 |
| T2 | 接口/验收节 L81 | "新版 Golden Set……仍需完整在线采样" | 措辞需修正（过期） | cloud | 同 E1：10-16 已完成两轮在线；学习包 24 条完整在线质量与人审仍未完成。 | 同 E1 |
| T3 | §10 L75 | "2026-10-15 真实浏览器配本地模拟 API 验证……尚未真实后端+在线模型浏览器联调" | 有证据 + 待人工 | offline（浏览器 mock 走查） | 措辞如实标注"模拟 API"；10-15 晚些时候做过一次真实后端+桩模型的浏览器复核（UPGRADE 文档），真实在线模型浏览器 E2E 仍未做。 | Wave 3 QWEN-331 Playwright E2E |
| T4 | §4 | MCP `mcp==2.3.0` 只读、生产启动器待验收 | 有证据 | offline | `requirements-mcp.txt` 钉 2.3.0 ✓；协议测试在 enterprise 可选步骤；"生产启动器和真实部署仍待验收"表述正确。 | 保持 |
| T5 | 其余十模块"职责/顺序/边界"段 | 各模块能力与"不是××"边界 | 有证据 | offline（契约）为主 | 抽查与会话记忆（3 条完成 Run）、检索 3 次上限、Reviewer 一次返工、只读工具白名单、租约/幂等语义均与代码一致；今日便携套件重跑支持。 | 保持 |

## 4. 竞赛/演示材料（V1 时代，对外仍可见）

> 这批文档的口径是 2026-06~09 竞赛期，与"V2 旗舰 + V1 兼容/演示"的当前定位不一致，是**最容易造成误读的区域**。总建议：每篇顶部加"历史竞赛材料，数字不描述当前 V2 主线"横幅，并修以下硬数字（归 QWEN-103/Wave 4）。

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| D1 | docs/00-评委30秒导览.md L9/L100 | "12 个 Agent + 1 个 Orchestrator"（并注 `*Agent(BaseAgent)` 共 12 子类） | 措辞需修正 | offline | 本轮实测 `class *Agent(BaseAgent)` 子类 **16** 个（含 critic/debate/evaluator/safe_decline 等实验角色）；"12"为旧清单。 | 重列当前清单或标注"演示主线 12 角色，另有实验角色" |
| D2 | 同上 L101 | "API 端点 90 路由（实测 grep）" | 措辞需修正（过期） | offline | 本轮实测 `@router.(get/post/put/delete/patch)` 装饰器 **187** 个（v1+v2 全量）。"90"为旧值。 | 更新口径（并区分 V1/V2、白名单内外） |
| D3 | 同上 L41/L107 | "真 6 种产物" | 措辞需修正 | offline（V1 实验） | `services/multimodal/` 实有 code_sandbox、manim、mermaid、ocr、pptx、tts、video（+SVG）≥7 类；且均属 V1/实验，非 V2 主线能力。OCR/视频未纳入其计数口径。 | 重计并标注"V1 实验能力" |
| D4 | 同上 L40/L90 | "3 个可发表原创"、"9 种学习者类型"、"10 创新点" | 愿景/自评 | —（无外部核验） | 学术性主张未经同行验证；"9 种类型"未逐行核代码（spot-check 未做）。 | 不作为工程事实；如保留加"自评"限定 |
| D5 | docs/06-演示视频脚本 L32/L148 | "12 个 Agent""8 个维度画像""完整实现赛题 5 大功能" | 愿景/自评（赛题口径） | — | 与 D1 同源；赛题对标话术，非当前产品宣称。脚本本身（视频）未录制。 | 横幅标注历史赛题口径；演示视频属 QWEN-402 |
| D6 | docs/DEMO_5_MINUTES.md L5/L84 | "下文质量数字仅为旧版 66 条在线基线（历史）"；64/66、Recall 95.83% 等 | 有证据-历史 + 措辞需复核 | cloud | 该文档**诚实标注历史口径**（好）；但"新版 76 条待真实验收"一句过期（同 E1）；64/66 原始报告未随仓库发表，只在 `docs/UPGRADE_IMPLEMENTATION_STATUS.md` 与 1.x 记录中转述。 | 更新 76 条状态；旧 66 条报告若继续引用应补脱敏汇总文件 |
| D7 | docs/TripleU-7分钟演示视频剧本 / 教师端2分钟剧本 | 演示流程与数字 | 待人工 | human | 未对照当前 UI 走查；视频未录制。 | Wave 4 与 QWEN-402 一并处理 |

## 5. 状态/交接类文档（记录型，允许保留历史原貌）

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| S1 | OPTIMIZATION_STATUS_2026-10-18 | 便携套件 346 passed / 1 skipped（35 文件） | 有证据-历史 | offline | 本轮 CI 清单为 37 文件，实测 **369 passed / 1 skipped**（见 report.md）；文件集合不同，不构成矛盾。 | 状态文档不回改；新日期新文档记录 |
| S2 | 同上 | 远端 CI run #17/#18 全绿；主计划注记 #19 全绿 | 需复跑（远端复核） | —（CI 环境） | 本机无 gh CLI，未能程序化验证 run 结论。 | Wave 1 起用网页或 CLI 复核并记录 URL |
| S3 | 同上 | 企业合同 353 passed / 0 failed（真实 PG/Redis 一次性容器） | 有证据-历史 | pg | 10-18 实测记录；本轮未重跑（约束：不默认启停容器）。 | QWEN-105 复跑 |
| S4 | 同上 | Linux 锁容器内 66 passed | 有证据-历史 | offline（Linux 容器） | 同上；nightly 远端记录待复核（R20）。 | QWEN-002→nightly 分层执行时复核 |
| S5 | 同上 | 本机生产栈 211.3s 构建启动 + 边界全通过 | 有证据-历史 | prod（仅本机） | 明确写了"不等于公网生产验收" ✓。 | 保持该限定 |
| S6 | 同上 | 费用记录：Redis 预留 188.38/200 元保守额度；"不是账单"；structured-output 费用 unknown 不写 0 | 有证据 | cloud | 符合"费用未知写 unknown"硬约束。 | 保持 |
| S7 | OPTIMIZATION_HANDOFF_2026-10-18 §5 | "当前工作区提示词版本 v2.6" | 措辞需修正（过期） | offline | 交接时快照为 v2.6；现为 v2.8。交接文档是历史件，不改正文。 | 无动作（本台账标注即可） |
| S8 | `docs/TripleU平台全功能思维导图.md` L550/L1231、`docs/10-学术与工程创新对照表.md` L490-491、`THIRD_PARTY_NOTICES.md` L425 | "React 内嵌应用：`frontend/integrated-map-src/src`"、"代码主体 `LabView.jsx`，由 Vue 以 iframe 嵌入" 等指向具体源码文件的表述 | **代码缺失（测试已隔离，措辞仍待修正）** | offline | 本仓库无 `frontend/integrated-map-src/`（`git ls-files` 无匹配、无 `.gitmodules`；Lead 复核 `git log --all` 亦无记录），只有其构建产物 `frontend/public/integrated-map/assets/*`（2 个文件）；`frontend/src/views/CockpitView.vue` 也不存在（后端 `cockpit.py` 与前端 `api/cockpit.ts` 在）。QWEN-121 处置：`git mv` **17 个**依赖缺失源码的测试到 `frontend/tests/_orphaned/`（只移不删，附逐文件缺失路径清单，其中 `demoLearnerName.test.mjs` 另与 `src/constants/companion.ts` 的 `GENERIC_LEARNER_NAMES` 设计冲突）；其余 17 个文件 `node --test tests/*.test.mjs`（node v24.13.0）实测 **21 顶层结果全通过 / 0 failed / exit 0**，已接入 CI frontend job（无 `|| true`）。**Lead 裁定（14:40 [REVIEW]）：两处语义改写保留**，无需回退；观察项：`.db-weak-kp-*` 死样式待清理或恢复薄弱点列表；若未来产品要求首页轨道图则回退测试并开产品任务。合并后 main run **#21** 在 node 20 复验通过（`remote`）。 | 源码来源结论归 QWEN-401；孤儿测试与 nightly 复核归 QWEN-343；文档正文措辞修正归 QWEN-103（不得把构建产物说成有源码） |
| S9 | `THIRD_PARTY_NOTICES.md` L453-456 | "59 tracked files under `frontend/public/integrated-map/pixel-campus/` 已在工作树删除但未暂存" | 措辞需修正（过期） | offline | 本轮实测该路径 `git ls-files` = **0**（去重已提交），磁盘只剩 14 个目录、**0 个文件**（`find -type d` = 14，`find -type d -empty` = 12 个叶子空目录，根目录与 `layers/` 只含子目录；Git 不跟踪空目录，`git status` 干净）；同文档 L37 的 30 个 `frontend/public/assets` 陈旧 React 产物计数仍一致。属 Wave 4 许可清点输入。 | QWEN-401 重跑清点后更新该行；本轮不改文档正文 |

## 6. 许可与素材

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| L1 | THIRD_PARTY_NOTICES.md | 151 Python 组件 / 5 UNKNOWN（均未安装，不猜测） | 有证据 | offline | 抽查文档表头数字自洽；UNKNOWN 处理符合"不猜测"约束。 | 保持 |
| L2 | 同上 | 95 个 Web npm 组件 / 285 桌面 npm 组件 | 有证据-未复点 | offline | 本轮未重跑清点脚本；结构（19 runtime + 266 dev）有说明。 | QWEN-003（依赖/许可基线）复点 |
| L3 | 同上 | 126 受跟踪媒体文件，其中 125 无来源证明 | 有证据 + 待人工 | human | 文档如实标注"需人工补齐来源/法务审查"；GPL/LGPL 项未下结论 ✓。 | QWEN-401 人工闭环 |
| L4 | README L219 | 代码 MIT | 有证据 | — | `LICENSE` 已跟踪。 | 保持 |

## 7. 主计划（QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md）自身数字

| # | 声明 | 状态 | 依据与说明 | 建议动作 |
|---|---|---|---|---|
| P1 | "189 个测试文件" | 有证据 | 本轮 `find tests -name 'test_*.py'` = 189 ✓（a 124 / b 42 / integration 9 / regression 5 / benchmarks 4 / 根 5）。 | — |
| P2 | "23 个 Vue 视图" | 有证据 | `frontend/src/views/*.vue` = 23 ✓。 | — |
| P3 | "27 个 API 模块" | 措辞需修正 | 实测 `backend/app/api/v1/*.py`（26，不含 `__init__`）+ `v2/*.py`（4）= 30 个模块文件；口径待统一定义后修正。 | 计划文下次修订时改数 |
| P4 | "CI 只跑约 38（quality）+ 约 30（enterprise）" | 措辞需修正（轻微） | 本轮解析 `ci.yml`：quality 便携清单 37 文件、enterprise 37 文件 + MCP 1（独立步骤）。QWEN-120 收口后 enterprise 为 **38** 文件（补入 `test_v2_retrieval_postgres.py`）。 | 计划文下次修订时改数（38 + 38 + MCP 1） |
| P5 | "基线 main 工作区干净、run #19 全绿" | 有证据（工作区）/ 需复核（CI） | 本轮 `git status --short` 干净 ✓（Wave 0 建分支前）；run #19 同 S2。 | 同 S2 |

---

## 汇总：本 Wave 需要动的条目（按归属）

1. **README**（QWEN-103 执行，Wave 1）：R9/R13（"在线契约"加注）、R11（用最新复跑数替换或加环境注记）、R17（企业级边界一句）、R20（nightly 远端记录）。
2. **evals/README.md**：E1 过期句。
3. **V2_TEN_MODULE_IMPLEMENTATION.md**：T1 版本号、T2 验收状态句。
4. **竞赛材料横幅**：D1–D7 统一加"历史赛题口径"标注；硬数字（12 Agent→16、90 路由→187、6 种产物）修正。
5. **已按 Lead 裁决执行（QWEN-121，方案 A）**：S8 —— 17 个依赖未提交源码的前端测试 `git mv` 到 `frontend/tests/_orphaned/`（只移不删），4 个过期断言按当前源码修正，CI frontend job 增加 `node --test tests/*.test.mjs`（本机 21/21 通过、exit 0）。**注意**：其中 2 个测试的语义被改写（`dashboardChineseTimeline` 的薄弱点列表断言、`homeOrbitCentering` 的首页 orbit 断言），因为它们指向本仓库不存在的 UI；如你认为该 UI 属应恢复的产品功能，请回退这两处并转为产品任务。
6. **不动**：所有诚实的历史归档（S 系列、E3–E6）与"未验证"标注——它们是本项目证据文化的资产。

**Wave 0 首轮未修改任何被核对文档的正文**（修正动作属 Wave 1 QWEN-103，需配套 CI 验证）；收口补丁（QWEN-004 / QWEN-120）只改测试期望、测试 skip 与 CI 清单，未改产品行为，结果见 [OPTIMIZATION_STATUS_2026-10-19.md](OPTIMIZATION_STATUS_2026-10-19.md) §六。台账中所有"有证据"结论的复跑证据见 `output/qwen-baseline-2026-10-19/report.md`（本地，Git 忽略）。
