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
| R3 | L25 | "PostgreSQL 检查点和执行租约实现断线恢复" | 有证据 | offline + pg | 检查点跨进程恢复、租约、API 崩溃恢复测试在 CI enterprise 与 2026-10-18 一次性容器（353 passed）验证；今日 SQLite 便携子集复跑通过。 | 保持；PG 组合已由 QWEN-105（2026-10-22）在本机一次性容器复跑：`test_learning_checkpoint_postgres.py`、`test_run_leases.py`、`test_postgres_api_recovery.py` 均在 38 文件 / 364 passed 两轮内，见 §14 |
| R4 | L27 | V2 旗舰链路（受限规划→Tutor→Practice→Reviewer→一次返工→按需人审） | 有证据 | offline（契约）+ cloud（单次采集） | 代码 `learning_package.py`（现 v2.9，QWEN-211b；**该 cloud 证据采集时为 v2.8**）+ 便携套件今日 369 passed；真实后端 13 条标准场景采集通过（cloud 历史）。契约测试不等于内容质量。 | 保持 |
| R5 | L29 | "`depends_on` 是未执行的兼容字段，不提供 DAG 依赖调度" | 有证据 | offline | 与 `orchestrator.py` 实现一致；README 主动降级表述，正确示范。 | V1 `depends_on` 二选一处置属 QWEN-212 |
| R6 | L31 | "三组对照已记录 72 次真实模型运行"；"双人质量复核尚未完成" | 有证据 | cloud + 待人工 | `evals/results/ablation-fixed-evidence-20261017.md`：24 任务 × 3 组 = 72 次，真实 DeepSeek Flash；人工评分确实未完成，措辞诚实。 | 保持（这是正确的"不宣称"范例） |
| R7 | L39 | "76 条新版 Golden Set 中 74 条通过" | 有证据-历史 | cloud | 2026-10-16 第二轮在线验收（`UPGRADE_IMPLEMENTATION_STATUS.md` 最终批）；脱敏汇总 `evals/results/qa-golden-v2-summary.json`（74/76、pass_rate 0.9737）。逐例原始记录只在本地 `output/`，未上传。 | 保持，但建议加"2026-10-16 历史"角标（L48 已有总说明） |
| R8 | L40 | "真实 PostgreSQL 恢复组合 15/15" | 有证据-历史 | pg | 2026-10-16 PG 专项（检查点跨进程、API 崩溃恢复、摄取幂等、向量版本检索、续跑）15/15；10-18 又跑 353 passed 企业组合。本轮未重跑。 | 已复跑（QWEN-105，2026-10-22，`pg`）：这五个类别所属文件全在 CI `enterprise-contract` 38 文件清单内，本机一次性容器两轮 **364 passed / 0 failed / 0 skipped**。注意口径不同——**不是**按 15 项为单位复现，而是更宽的 38 文件清单，故 15/15 原值保留为历史。见 §14 |
| R9 | L41 | "13 个在线契约场景 13/13" | 有证据-历史 + 措辞需修正 | cloud（采集）→ offline_replay（评测） | `evals/results/learning-package-v1-summary.json`：`evaluation_mode=offline_replay`、`prediction_kind=recorded`；13/13 指**契约**（结构/引用/预算），且 `human_review_coverage=0.0`。"在线契约"字样易被读成在线质量。 | 措辞改为"真实后端采集的 13 条契约场景（回放评测；非内容质量）" |
| R10 | L52–55 | 74/76（97.37%）、Hit@5 95.83%、Recall@5 94.79%、引用 100%/100% | 有证据-历史 | cloud | 与脱敏汇总 JSON 逐项一致（0.9583/0.9479/1.0/1.0）。README L62 已声明为历史汇总；引用"有效率"= ID 存在性（L31 已自声明非事实支持）。 | 保持 |
| R11 | L56 | "本地离线测试 2153 passed, 18 skipped" | 有证据-历史；本轮已复跑并收口 | offline | 原值：2026-10-16 Windows **Python 3.10** 全量 `pytest tests/`（626 s）。本轮 2026-10-19 在 Python 3.12.15（conda `evidence-agent-py312`）复跑全量：首轮 **2234 passed / 2 failed / 19 skipped（650.31 s）**；两处失败定位为① Windows kombu filesystem broker 缺 pywin32、② TTS 回退 `edge-tts` 未列入测试允许值，均属环境/测试期望而非 V2 主线回归。QWEN-004 收口（只改测试：补 `edge-tts` 允许值 + Windows 缺 `pywintypes` 条件 skip）后复跑 **2235 passed / 0 failed / 20 skipped（612.61 s）**。明细见 `output/qwen-baseline-2026-10-19/`（本地，Git 忽略）。 | README 更新为最新复跑口径（2235/0/20，py3.12.15 Windows）并加"运行环境（py 版本/平台）"注记；措辞修正动作归 Wave 1 QWEN-103 |
| R12 | L57 | PostgreSQL 专项 15/15 | 有证据-历史 | pg | 同 R8。 | 同 R8；README L57 已加 QWEN-105 复跑注记（38 文件 / 364 passed，`pg`），原 15/15 未删除 |
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
| E7 | 双人盲评/裁决工具（`scripts/prepare_ablation_*` **新增** `scripts/human_eval/` 五入口 + `backend/app/evaluation/human_agreement.py`） | "已实现工具，评分待真人" | 有证据（两套工具）+ 待人工（评分） | offline | 旧工具测试 `test_ablation_review_packets.py` 与 QWEN-101 新测试 `test_human_agreement_statistics.py`/`test_human_eval_toolkit.py`（27 用例）均本机通过；协议见 `docs/HUMAN_EVAL_PROTOCOL.md`；**无任何文档宣称评分已完成**，新包生成时 `scores` 恒为 `null`。旧材料（2026-10-17）A/B 同序、26 item 全为 `null`，只作历史观察、不重算不混用 | 评分执行需真人 2 名 + 分歧时第 3 名；"20 题"按 item 级口径（Lead 裁决 5） |

## 3. docs/V2_TEN_MODULE_IMPLEMENTATION.md（自称"描述当前代码"）

| # | 位置 | 声明 | 状态 | 证据等级 | 依据与说明 | 建议动作 |
|---|---|---|---|---|---|---|
| T1 | §8 L58 | "`PROMPT_VERSION=learning-package-v2.4`" | 措辞需修正（过期） | offline | 复核当时代码为 **v2.8**（`learning_package.py:20`；现 **v2.9**、`:25`，见 §25；QWEN-231 新增两行 import 后行号由 `:23` 后移）；`WORKFLOW_VERSION=learning-workflows-v2.3`（`run_lifecycle.py:29`）。文档头部日期 2026-10-15 未随后续批次更新。 | QWEN-103：全文按当前代码刷新版本号与批次差异 |
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
| S7 | OPTIMIZATION_HANDOFF_2026-10-18 §5 | "当前工作区提示词版本 v2.6" | 措辞需修正（过期） | offline | 交接时快照为 v2.6；现为 v2.9（QWEN-211b；当时复核记为 v2.8）。交接文档是历史件，不改正文。 | 无动作（本台账标注即可） |
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

## 8. QWEN-103 修正登记（2026-10-19，分支 `qwen/wave1-docs`，纯文档、零模型调用）

上方各行的"建议动作"列保留 Wave 0 的原始结论不回改；落地情况集中登记在本节。所有数字均为 2026-10-19 本机一手复跑（Windows + Git Bash + conda `evidence-agent-py312` / Python 3.12.15，离线 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none`；付费模型调用 0 次）。

| 条目 | 落点 | 修正内容 | 一手证据 |
| --- | --- | --- | --- |
| T1 | `docs/V2_TEN_MODULE_IMPLEMENTATION.md` §8 + 文首日期 | `learning-package-v2.4` → **v2.8**，并补 `WORKFLOW_VERSION=learning-workflows-v2.3` 的**正确路径**；文首更新时间改为 2026-10-19 并注明上一版 2026-10-15 | `learning_package.py:20`、`backend/app/api/v2/run_lifecycle.py:29`（台账原记 `run_lifecycle.py` 未带 `api/v2`，已纠正） |
| E1 | `evals/README.md` 文首 | 删除"76 条集……目前未完成真实云端验收"过期句，改为"2026-10-16 两轮在线验收、第二轮 74/76 + Hit@5/Recall@5/引用率"，并列出**仍未完成**项（学习包 24 条完整在线质量评测、逐 claim 人审、真人盲评）；同时补入 QWEN-102 的 12 题单臂结果指针 | `evals/results/qa-golden-v2-summary.json`（`evaluation_mode=online`、74/76）、`evals/results/independent-2026-10-19.md` |
| D1 | `docs/00-评委30秒导览.md` 一句话定位 + 统计表 | "12 个 Agent"→ **16 个 `BaseAgent` 子类**，并区分"演示主线 12 角色 / 其余为实验角色（critic、debate moderator、evaluator、safe_decline 等）" | `grep -rho "class \w*Agent(BaseAgent)" backend/app/agents/*.py \| sort` = 16（逐一列名核对） |
| D2 | 同上 | "90 路由"→ **187** 个路由装饰器，注明为 V1+V2 全量、且 V2 对外另需身份与课程授权白名单 | `grep -rho "@router\.(get\|post\|put\|delete\|patch)" backend/app` = 187 |
| D3 | 同上（对比表 + 统计表两处） | "真 6 种产物"→ **7 类产物模块**（新增 OCR、视频拼接；SVG 归为 Manim 占位输出），并标注"属 V1/实验能力，不计入 V2 学习包主线" | `ls backend/app/services/multimodal/` = `code_sandbox.py`、`manim/`、`mermaid/`+`mermaid_renderer.py`、`ocr/`、`pptx/`+`pptx_builder.py`、`tts_xunfei.py`、`video_xunfei.py` |
| D1–D3 附带 | 同上统计表其余三行 | 数据库表 **15 → 37**；知识库章节 **24（AI 20 + Python 4）→ 38（AI 20 + Python 18）**，并注明 `computer_work` 已注册但正文 0 章；测试用例 **1186 → 2284 项**（2263 passed / 1 failed / 20 skipped）并附环境注记 | `models.py` `__tablename__` = 37；`ls knowledge_base/*/chapters/*.md` = 20 / 18；全量 `pytest tests/` 679.38 s（191 个测试文件） |
| R9 / R13 | `README.md` 核心能力表 + 实测指标表 | "13 个在线契约场景 13/13"与"学习包标准在线契约 13/13"均加口径注记：**真实后端采集后的离线回放契约评测（结构/引用/预算），非内容质量、不含人工评分** | `evals/results/learning-package-v1-summary.json`（`evaluation_mode=offline_replay`、`human_review_coverage=0.0`） |
| R11 | `README.md` 实测指标 | "本地离线测试 2153 passed, 18 skipped"→ 最新复跑 **2263 passed / 1 failed / 20 skipped**（2026-10-19，Windows + py3.12.15，679.38 s，191 文件），并在同一行说明唯一失败是宿主 `.env` 配置期望所致、Linux CI 无 `.env` 时全绿；保留上一轮 **2235 / 0 / 20**（189 文件，612.61 s）作对照 | `output/qwen103-2026-10-19/logs/pytest-full.log`（本地，Git 忽略）；失败用例 `tests/a/test_embedding_provider.py:39` 断言 `batch_size==10`，本机 `.env` 配 `20` |
| R17 | `README.md` 生产部署链接处 | "企业级"加边界一句：仅指本机 Compose 全栈构建/启动与边界验收通过，**公网 TLS、域名、备份与监控未验证** | 台账 R17 原判（`prod` 仅=本机栈）；未新增任何公网宣称 |
| S8 | `docs/TripleU平台全功能思维导图.md` §3.11 与"代码位置"节、`docs/10-学术与工程创新对照表.md` 工程位置节 | 三处指向 `frontend/integrated-map-src/**` 的表述统一加注：**该源码树不在本仓库**，只有构建产物 `frontend/public/integrated-map/assets/`（2 个文件），不得把产物说成有源码；来源结论归 QWEN-401，17 个孤儿测试隔离于 `frontend/tests/_orphaned/` | `git ls-files frontend/integrated-map-src` = 0；`git ls-files frontend/public/integrated-map/assets` = 2；无 `.gitmodules` |
| S9 | `THIRD_PARTY_NOTICES.md` working-tree 段 + G9 行 | 原"59 个跟踪文件已删除未暂存 / 86 个文件修改（工作树脏）"改为**已提交**：该路径跟踪 0 文件、磁盘 0 文件、14 个目录（12 个空叶子目录，Git 不跟踪空目录故状态干净）；正版素材仍在 `frontend/public/pixel-campus/`（51 PNG + 8 `.gitkeep` = 59 跟踪文件）；素材溯源清点本身仍归 QWEN-401 | `git ls-files frontend/public/integrated-map/pixel-campus` = 0；`find` = 0 文件 / 14 目录 / 12 空叶子；`git ls-files frontend/public/pixel-campus` = 59 |
| E1 附带 D6 | 台账 D6 指出 `docs/DEMO_5_MINUTES.md` 仍有过期"76 条待真实验收"句 | **本轮未改**（未在 Lead §3-23 清单内），登记为遗留项 | 待 Lead 单点确认后再动，避免顺手扩大改动面 |

新增发现（本次复跑暴露，未修复、只登记）：

1. **`tests/a/test_embedding_provider.py` 对宿主配置敏感**：用例 monkeypatch 了 `EMBEDDING_BASE_URL/KEY/MODEL/DIM`，却没 patch `EMBEDDING_BATCH_SIZE`，于是断言 `batch_size == 10` 读到本机 `.env` 的真实值 `20` 而失败。这是 Wave 0 全量 2235/0/20 之后**新出现**的红点，成因是 2026-10-19 15:20 前后把 Qwen embedding 配置合并进 `.env`（Lead 操作），属测试期望缺口而非产品回归；CI（无 `.env`）仍绿。修法是一行 `monkeypatch.delenv/setenv`，但那是测试代码改动，**超出 QWEN-103 的纯文档范围**，请 Lead 派单（建议归 QWEN-343 或 Wave 2 的测试隔离项）。
2. **`reports/` 未被 gitignore 的三点矛盾**（已在 `evals/LEARNING_PACKAGE_EVAL.md` 正文登记）：脚本默认输出 `ROOT/reports/learning_package_offline_report.json`（`scripts/evaluate_learning_package.py:26`）× `.gitignore` 无 `reports/` × 文档要求"报告只放本地 `output/reports`"。当前 `reports/` 不存在、跟踪 0 文件，故尚未泄露；整改需改 `.gitignore` 或改脚本默认值，属代码/配置动作，归 QWEN-401/403。本轮只在文档里写清矛盾与临时规避（显式 `--output`）。
3. **口径纪律**：日期型归档与交接文档（`docs/OPTIMIZATION_HANDOFF_2026-10-18.md` 仍写 v2.6）按"保留历史原貌"原则**不回改**，只在台账登记；本轮只刷新自称"描述当前代码"的文档。

## 9. QWEN-106 测试隔离收口登记（2026-10-21，分支 `qwen/wave1-health`，零模型调用）

执行边界：未读未打印 `.env`；未创建/重启容器；未改产品代码；`ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（CI 同口径）通过；`git diff --check` 干净。

### 9.1 已修（测试代码，最小改动）

| 条目 | 落点 | 改动 | 一手证据 |
| --- | --- | --- | --- |
| ① embedding 宿主配置隔离 | `tests/a/test_embedding_provider.py:24` | 补 `monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)`。用例此前 patch 了 base_url/key/model/dim 却漏了 batch_size，于是 `assert provider.batch_size == 10` 读到本机 `.env` 的 `20` | 单文件本机带真实 `.env` 复跑 **1 passed / 0.19s**（`-o addopts= --benchmark-disable`）；provider 在构造时读 `os.getenv`（`backend/app/services/embedding_provider.py:34`），故 delenv 生效 |
| ② manim 用例诊断信息 | `tests/integration/test_manim_fallback.py:133-137` | 只给 `assert fa["used"] is False` 加失败消息（打印 `fallback_assets`、`manim_success`、`error`、`metadata`），**断言强度不变、产品行为不变** | 加消息后一次被阻断的复跑直接把根因打到屏幕上：`reason='manim_render_failed'` |

### 9.2 定位结论：`test_code_only_skips_fallback` 不是"顺序依赖"，而是**外联依赖**

判定链条（全部本机复现）：

1. `_detect_manim_needs_fallback()` 的第一个触发条件是 `not envelope.success`（`backend/app/api/v1/artifacts/multi_with_fallback.py:70`）。
2. `_gen_manim()` 在 Level‑1 agent 视频被质量门拒绝、且 Level‑2 只产出脚本（无 `.mp4`）时返回 `success=False` 的 envelope（`multi.py:2719` 记录 `画面与旁白时长偏差 2.49s，超过允许的 2.00s，已阻止发布`；`multi.py:2868` 返回 `success=False`）。
3. 因此该用例的绿/红取决于**真实媒体链路与真实 LLM 外联是否可用**，而不是产品逻辑：在既未设 `A3_OFFLINE_DEMO` 也未设 `LLM_PROVIDER=none` 的条件下，探针记录到 3 次外联尝试，端点类别为 `api.deepseek.com:443 /v1/chat/completions`，同一用例 **1 failed / 50.71s**。
4. 补上仓库文档口径的两个环境变量（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none`）后，同一用例 **1 passed / 45.57s，探针 `outbound attempts=0`** —— 即离线态下该用例稳定通过，无需改测试或改产品。
5. 对照：同一文件不加任何护栏整体复跑 **9 passed / 248.98s**（能出绿，但代价是真的向外联）。

**结论与归属**：产品侧"脚本态 manim 一律 `success=False`"与用例侧"`include_manim=false` 就不该触发兜底"这两条语义在 `types=["manim"]` 时相互矛盾——绿只在离线开关生效时出现。本轮**不改产品行为、不放宽断言**（Lead 边界），登记为遗留项，建议开一张代码卡处理（要么让用例显式设 `A3_OFFLINE_DEMO/LLM_PROVIDER=none`，要么把 `types=["manim"]`+`include_manim=false` 的期望改成断言 `reason=='manim_render_failed'`，二者都属产品语义决策，需 Lead 定）。

### 9.3 我本轮自造的两个测量错误（如实登记，避免下轮重犯）

1. **`DATABASE_URL="sqlite:///$PWD/..."`**：Git Bash 下 `$PWD` 是 `/d/xunfei/...`，拼出的 URL 变成 `sqlite:////d/xunfei/...`，SQLite 实际打开的是仓库外的 `D:\d\xunfei\...`。于是首轮全量多出 **6 个红点**，报错全是 `sqlite3.OperationalError: no such table: profiles/knowledge_points`（`tests/a/test_cockpit_endpoint.py` 4 例、`tests/a/test_cockpit_branches.py` 1 例、`tests/a/test_collaboration_resource_regressions.py` 1 例）。**这不是产品缺陷也不是网络所致**：探针在同一批用例上记录 `outbound attempts=0`；去掉这个自造的 `DATABASE_URL`（用仓库默认 DB）后同批文件 **97 passed / 34.99s**。该拼写错误在**仓库外**落了 3 个 `.db`（`D:\d\xunfei\evidence-first-learning-agent\output\qwen106-2026-10-21\`：`full.db` 3,174,400 B / 37 表、`full-seeded.db` 782,336 B、`legacy-full.db` 0 B，均为本轮 22:41–23:01 新建）。**Lead 已于 2026-10-21 23:50 左右删除这 3 个游离文件**（只删 `.db`，保留目录内其他文件）；这是测试命令错误，不是产品/测试缺陷。
2. **漏设离线开关**：见 9.2 第 3 点，我一度据此推断"此前标注 `offline` 的全量复跑可能发出过真实调用"。该推断**已被本轮实验推翻**：`docs/CLAIMS_LEDGER.md` §8 记录的 QWEN-103 口径本来带 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none`，按其口径复跑时探针 `outbound attempts=0`，QWEN-103 的 `offline` 标注成立。我在 §4 的中间播报里下过相反结论，需按本节口径撤回。
### 9.4 本轮实测数字（README 与导览表以此为准）

| 运行 | 集合 | 结果 |
| --- | --- | --- |
| 全量 `pytest tests/`（离线 + 探针，QWEN-106 官方口径） | 191 文件 / 2284 项 | **2264 passed / 0 failed / 20 skipped**，834.21 s；探针 6 次外联尝试 / 2 个 IP 全部阻断，无失败用例因阻断产生 |
| 对照 QWEN-103（2026-10-19） | 同 191 文件 | 2263 / 1 / 20，679.38 s；+1 passed 恰为 ① 的隔离修复 |

日志：`output/qwen106-2026-10-21/logs/pytest-full-official-guarded.log`（Git 忽略）。上表两处"探针未逐条归属"的限制已在 `docs/TEST_MATRIX.md` §6 同批行内写明。

### 9.5 Lead 裁定（2026-10-21）

1. **QWEN-106 验收通过**：Lead 独立复跑全量 **2264 passed / 0 failed / 20 skipped / 816.03s**（无探针），与 Qwen 的 834.21s（带探针）互相印证；embedding `.env` 隔离修复接受。
2. **manim 语义选方案①**：测试显式设 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none`，按现状接受 `reason='manim_render_failed'`；**本轮不改产品行为**。方案②（脚本态改为 `success=True/script_only`）需产品需求后再做。
3. **游离 `.db` 已删除**：Lead 已移除 `D:\d\...` 下 3 个误建文件；后续全量务必使用仓库内 `sqlite:///./output/<dir>/...` 绝对/相对路径，不要用 Git Bash `$PWD` 拼 URL。
4. **QWEN-107 派发**：测试确定性 + 探针 per-attempt 归属（6 次外联尝试/2 IP）；零模型调用、不改产品。**QWEN-104 成本可见性仍优先**。

## 10. QWEN-104 成本/用量可见性登记（2026-10-22，分支 `qwen/wave1-cost`，零模型调用）

### 10.1 交付内容

| 文件 | 动作 | 说明 |
|---|---|---|
| `backend/app/services/run_usage.py` | 新增 | 纯投影 + 聚合：把 `agent_runs.metadata["result"]["budget"]`（由 `usage_meter.record_model_usage` 写入）读成一份用量/成本摘要。不查库、不调模型、**不重算任何价格** |
| `backend/app/api/v2/run_usage_admin.py` | 新增 | 管理端只读 2 条路由：`GET /api/v2/admin/run-usage`（分页 + 当前页聚合）、`GET /api/v2/admin/run-usage/{run_id}`。每条先取真实登录会话，再 `authorize_reviewer` 要求 teacher/admin；持久层故障 503、未知 run 404 |
| `backend/app/api/v2/router.py` | +2 行 | 挂载新 router |
| `tests/a/test_run_usage_admin.py` | 新增 | 9 用例（四态投影、聚合、分页、角色门禁、404/503、tariff 环境变量不影响输出、响应不泄漏请求正文） |
| `.github/workflows/ci.yml` | +1 行 | 新测试文件进 portable V2 contract suite（便携段 39 → 40 文件）；**pg/enterprise 段未扩** |

证据等级：全部 `offline`（本机一手复跑与本机测试），无任何付费模型调用；未读未打印 `.env`；未创建/重启容器；未推 main。

### 10.2 "缺数据写 unknown"的实现口径

- `usage_status` ∈ `measured` / `partial` / `unknown`；`cost_status` ∈ `estimated` / `unknown`。
- `cost_cny` **只在 `estimated` 时非空**，其余一律 `null`——沿用 `scripts/collect_ablation.py:111-121` 既有约定，避免把未知当零成本。
- provider 没返回 usage 的调用数走 `usage_unknown_calls`；有实测 token 同时又有未知调用 → `partial`，聚合时单列 `runs_without_token_data` / `runs_without_estimated_cost`，**未知项只计数，不参与求和**。
- `budget_recorded=false` 区分"这条 Run 从未记账"与"记了账但 provider 没给 usage"；`cost.reason` ∈ `cost_not_recorded` / `no_cost_amount_recorded` / `cost_status_invalid`。
- 投影层只搬持久化值：测试证明设与不设 `V2_LLM_INPUT_CNY_PER_MILLION` / `V2_LLM_OUTPUT_CNY_PER_MILLION`，同一 Run 的响应逐字段相同（即本卡不引入任何单价）。

### 10.3 本轮新实测推翻的既有结论（如实登记，不回改 §9 原文）

1. **§9.2 / 矩阵 §6 的"离线开关下该 manim 用例稳定绿"不成立**。本轮两次全量（重构前 782.22 s、最终 731.42 s）在**已设** `A3_OFFLINE_DEMO=true LLM_PROVIDER=none` 且挂探针的条件下都失败，断言诊断给出 `error='画面与旁白时长偏差 2.09s，超过允许的 2.00s'` 与 `'… 2.17s …'`（阈值固定、抖动值逐轮变化）；同一用例单独离线跑仍是 1 passed / 45.57 s / `attempts=0`，本轮 2026-10-22 再单独复跑仍 1 passed / 46.33 s / `attempts=0`。结论改为：**质量门时长抖动**决定红绿，既非顺序依赖也非外联依赖。因此 Lead 2026-10-21 裁定的方案①（测试显式设离线开关）**不足以**给出确定性，QWEN-107 需在此之上再定；本轮未改产品、未放宽断言。
2. **我自己的无证据陈述更正**：会话中我曾说出"重构前首轮 2273 passed / 0 failed"，而该轮日志实际是 **1 failed / 2272 passed / 20 skipped（782.22 s，探针 6 次尝试 / 2 IP）**。该结论在读取日志之前就说了出口，属第二次"先说结论后找证据"，登记备查；已合并的 §9 数字不受影响。

### 10.4 数据可见性的真实限制（勿过度解读）

- 本机仓库默认 SQLite `data/a3_learning.db` 的 `agent_runs` 实测 **0 行**（只读查询，仅计数与分类，不打印内容），所以新端点在本机**没有真实 Run 可展示**；正确性证据只有测试构造数据这一级（`offline`）。
- QWEN-102 付费跑的用量写在评测 JSONL（`runs.jsonl` 的 `budget`）而**不落 `agent_runs`**，故"评测战役的成本可见性"需要另开一张卡，本卡未扩范围。

### 10.5 公共口径变化（按实测）

| 条目 | 旧 | 新 | 复核命令 |
|---|---|---|---|
| 路由装饰器 | 187（QWEN-103 核定） | **189** | `grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l` |
| 全量测试 | 2264 / 0 / 20（191 文件，834.21 s） | **2272 / 1 / 20**（192 文件 / 2293 项，731.42 s） | `pytest tests/`（离线口径见矩阵 §7） |
| CI 便携清单 | 39 文件 / 398 passed / 1 skipped | **40 文件 / 407 passed / 1 skipped**（56.35 s，`attempts=0`） | `ci.yml` 便携段逐条复跑 |
| 数据库表 / 知识库章节 | 37 / 38 | **37 / 38（未变）** | 本卡未加模型、未动知识库 |

### 10.6 明确未做（避免越界）

未加过滤参数（按用户/课程/时间）、未做评测 JSONL 视图、未扩 pg/enterprise CI 清单、未改产品语义、未改 §9 与 QWEN-103 已合并结论（只在 §10.3 补充新实测）。

## 11. QWEN-107 manim 方案②产品语义修正登记（2026-10-22，分支 `qwen/wave1-manim`，零模型调用）

### 11.1 交付内容（1 处产品代码 + 1 个既有用例文件）

| 文件 | 改动 |
|---|---|
| `backend/app/api/v1/artifacts/multi.py:2785-2880`（`_gen_manim` Level 2 收口） | 新增 `render_requested = bool(req.manim_render or req.include_manim)`（`:2787`）；在"没有可播放 MP4"的脚本态分支里，**未请求渲染且 `generate_manim` 自身成功**时（`:2867`）返回 `success=True`、`video_status="script_only"`、`rendered=False`、`playback_status="unavailable"`、`downloads=[]`；请求了渲染则保持原 `success=False` 与 `error` 文案不变 |
| `tests/integration/test_manim_fallback.py`（+5 用例，`TestScriptOnlySemantics`） | 用 monkeypatch 钉住 Level 1/Level 2/质量门三条 seam，给出 5 项确定性回归（见 11.3），不依赖本机媒体链路、不产生任何网络/模型调用 |

### 11.2 未做的事（边界）

- **没改质量门阈值**：`MIN_PLAYABLE_VIDEO_SECONDS=3.0`、`MAX_AV_DURATION_DRIFT_SECONDS=2.00` 原文未动，`_video_quality_gate` 本体未动（测试里的 `rejected/passed` 返回值是 monkeypatch 伪造，不是产品实现）。
- **没改其他产物语义**：`include_manim=true` 的渲染失败/质量门拒绝仍 `success=False` 并触发兜底；`mermaid`/`tts`/`document`/`quiz`/`pptx`/`code` 路径零改动。
- **没加端点**：路由仍 **189**（`grep -rhoE '@router\.(get|post|put|delete|patch)\(' backend/app | wc -l` 实测）；没碰 `.github/workflows/ci.yml`、`.env`、质量门以外的降级逻辑。
- **没动 registry 清理行为**：脚本态仍从 registry 移除无文件记录，`downloads` 仍为空，避免"没有视频的记录"被当成可下载资源。

### 11.3 方案②的两条硬性回归（Lead 2026-10-22 指定）

| 断言 | 用例 |
|---|---|
| `include_manim=false` 确定性不触发 fallback | `test_script_only_is_success_when_render_not_requested`（Level 1 不可用 + Level 2 只出脚本）；`test_quality_gate_jitter_does_not_fail_unrequested_render`（复现历史抖动：Level 1 被质量门判 rejected，仍 `success=True`、`used=False`，且 `metadata.agent_video_quality.status="rejected"` 保留可审计原因） |
| `include_manim=true` 且质量门拒绝时仍失败/触发 fallback | `test_render_requested_and_gate_rejected_still_falls_back`（`success=False`、`video_status="rejected"`、`used=True`、`reason="manim_render_failed"`）；`test_render_requested_without_video_still_falls_back`（请求渲染却只拿到脚本 → 仍失败并兜底）；`test_render_requested_and_gate_passed_still_succeeds`（正路未被削弱：`success=True`、`rendered=True`、`used=False`） |

### 11.4 本轮实测事实（不做过度推断）

1. **抖动机器的第一手复现**：同一台机器、同一离线开关（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none`）、同一段只读脚本三次直接调用 `_gen_manim(include_manim=False)`（`output/qwen107-2026-10-22/probe_manim_envelope.py`）——第 1 次（产品落地前）质量门判 `rejected`（`av_duration_drift=2.25s`，视频 94.19 s / 旁白 91.94 s）→ 脚本态 `success=False`；第 2、3 次质量门放行（第 3 次存档读数 `drift=1.61s`，`output/qwen107-2026-10-22/logs/probe-manim-run3.txt`）→ `video_status='ready'` + MP4。结论：红绿由**媒体时长抖动**决定，与顺序、外联无关——与 QWEN-104 §10.3 的实测一致。诚实标注：只有第 3 次落了盘，前两次读数当时在终端，未单独存档。
2. **`generate_manim` 根本不返回 `script`/`code` 顶层字段**（`ResourceResult` 实测键集：`resource_id/type/filepath/data_uri/method/metadata/duration_ms/error/success`；讲稿正文只在 `metadata.generated_code`，本轮 3002 字符）。因此 `_gen_manim` 里 `content = r_dict.get("script") or r_dict.get("code") or ""` **恒为空**，脚本态的 `content` 改动前后都是 `None`。**本轮按 Lead 裁定只改 success/状态字段，没有顺手把讲稿塞进 `content`**——若要真正交付"可编辑讲稿"，需要另开一张卡决定 `content` 取哪个字段。
3. **`success=True` 不会被下游当成"视频已生成"**：`backend/app/agents/resource_generator_agent.py:94-112` 对 `rtype == "manim"` 走严格判据——必须是 `.mp4` filepath 或视频类 download **且** `metadata.playback_status == "ready"`；脚本态这三项都不满足，因此仍不会写入 `generated_resources`。前端同理：`frontend/src/views/ChatView.vue:1868-1870` 在 `playback_status === "unavailable"` 时不生成可播放媒体卡片。即"成功"表达的是**脚本产物交付成功**，不是"有视频可看"。
4. **全量数字**：2278 passed / 0 failed / 20 skipped（1095.22 s，192 文件 / 2298 项，探针 `attempts=6 unique_hosts=2` 全部阻断）。相对 QWEN-104 的 2272/1/20：既有红点转绿 + 新增 5 项 = 2278，逐项吻合。**证据等级：offline**。

### 11.5 探针 per-attempt 归属（Lead 指定为可选项，本轮完成）

`output/qwen107-2026-10-22/qwen_net_probe_attempts.py`（只读工具，未进 `tests/`、未提交）在阻断处补记"当前用例 + 阶段 + 线程 + 调用栈"，并用 `output/qwen107-2026-10-22/test_probe_selfcheck.py` 自检其归属能力（2 passed：能记录、且只归属到真正运行的用例）。全量第二跑用它复跑：

- **结果与官方跑一致**：2278 passed / 20 skipped（1198.51 s，官方跑 1095.22 s），`outbound attempts=6 unique_hosts=2` 完全同数——增强探针没有改变任何用例红绿。
- **6 次尝试全部归属到同 1 个用例**：`tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip`，阶段 `setup`，线程 `asyncio-portal-*`（非 MainThread，说明发生在异步入口里）。两个 IP 各 3 次。
- **探针记录的调用栈**：`knowledge_admin.py:247:upload_document` ← `knowledge_ingest.py:384:ingest_document` ← `knowledge_ingest.py:191:_persist_enterprise_version` ← `embedding_provider.py:63:embed_documents`。已核对 `embedding_provider.py:55-70`：该处是 `requests.post(f"{self.base_url}/embeddings", ...)`，外层 `attempts = max(1, min(max_attempts, 3))` 逐次重试，与"每个 IP 3 次"吻合（解析到两个地址，各跑满 3 次重试）。
- **端点类别**：embeddings 接口，**不是聊天/补全模型端点**；探针只记录 host/IP 与栈，未记录 URL 全文与请求体。`base_url` 的实际值来自本机配置，本轮**未读取 `.env`**，因此不写服务商名。
- **是否造成计费**：无。6 次 connect 全部被 fail-closed 探针阻断在 `socket.connect`（返回 `OSError`），出网字节数为 0，用例本身仍 passed。日志：`output/qwen107-2026-10-22/logs/pytest-full-attribution.log`。
- **本轮未做的事**：没改这个用例、没改 `embedding_provider.py`、没给用例加离线开关。这条"套件靠探针才离线"的事实是**既有行为**（QWEN-104 §10.3 与 QWEN-106 均记录过同一现象），要否把它变成显式离线（例如用例内 mock embeddings 或设 `EMBEDDING_*` 桩）请 Lead 裁定，属另一张卡的范围。

## 12. QWEN-107b 脚本态 `content` 交付登记（2026-10-22，分支 `qwen/wave1-manim`，零模型调用）

Lead 2026-10-22 裁定：脚本态 `success=True` 但 `content=None` 等于"成功了却没交付物"，属功能缺口，必须修。本节取代 §11.4 第 2 条所描述的**现状**（那条记录的实测事实——`generate_manim` 顶层无 `script`/`code` 字段、讲稿只在 `metadata.generated_code`——仍然成立并保留，只是产品不再把它当成"可以不给交付物"的理由）。

### 12.1 交付内容（1 处产品代码 + 1 个既有用例，无新增测试项）

| 文件 | 改动 |
|---|---|
| `backend/app/api/v1/artifacts/multi.py` | 新增模块级常量 `MANIM_SCRIPT_MISSING_ERROR`（`:2671`）；脚本态成功分支（`:2870-2898`）改为 `script = str((r_dict.get("metadata") or {}).get("generated_code") or "")`（`:2877`），非空则 `content=script`（`:2892`），为空/缺失则 `success=False` + `error=MANIM_SCRIPT_MISSING_ERROR` + `content` 留空 + `downloads=[]`（`:2878-2888`），不静默交付空产物 |
| `tests/integration/test_manim_fallback.py` | 只**扩展现有** `test_script_only_is_success_when_render_not_requested`：先断言 `content` 非空且含讲稿文本，再在同一用例内用 `code="   "` 复跑一次并断言 `success is False`、`error` 等于稳定错误常量、`content` 仍为空。`_level2` helper 增加 `code` 形参（默认值等价原内联字面量）。**未新增 `def test_` 用例**，故套件计数不变 |

### 12.2 未做的事（边界）

- **没改渲染态与失败态**：请求渲染时的质量门拒绝分支、`fallback_reason` 文案、`success=False` 语义一字未动；质量门阈值 `3.0 s` / `2.00 s` 未动；`multi_with_fallback.py`、`.github/workflows/ci.yml` 未动。
- **没加端点**：路由仍 **189**（`grep -rhoE '@router\.(get|post|put|delete|patch)\(' backend/app | wc -l`）。
- **没扩 `content` 的其它来源**：只取 Lead 指定的 `metadata["generated_code"]`；`metadata.generated_code` 上游已被 `generate.py:473-488` 截到 5000 字符，本轮未再加 1500 字符那类二次截断（渲染态分支的 `str(content)[:1500]` 保持原样）。
- **`evidence`/`cov`/`safety` 的输入未动**：`_enrich_with_safety_cov(str(content), ...)`（`multi.py:2807`）在两条分支之前执行，其 `content` 变量在脚本态仍取自顶层 `script`/`code` 字段（恒空），所以 CoV/Safety 校验的对象**不是**新交付的讲稿正文。这是既有实现的选择，本轮按 Lead 划定的最小范围没有改；若要"对交付的讲稿做安全/一致性校验"，需另开卡裁定。
- **行号漂移说明**：常量插在 `_gen_manim` 之前使其后所有行号 **+3**，故 §11.1 里 `multi.py:2785-2880` / `:2787`（`render_requested`）/ `:2867`（脚本态成功分支）应读作 `:2788-2883` / `:2790` / `:2870`。§11 正文按"旧论断保留"原则未回改。

### 12.3 本轮实测（证据等级：offline）

| 项 | 结果 |
|---|---|
| 定向 `tests/integration/test_manim_fallback.py` | **14 passed / 451.60 s**（`-p sandbox_tmpdir_shim -p qwen_net_probe_attempts`，`outbound attempts=0 unique_hosts=0`）；用例数仍 14，与扩展前一致 |
| 全量 `pytest tests/` | **2278 passed / 0 failed / 20 skipped / 756.16 s**，`192` 个测试文件 / `2298` 项（2278+20，与 QWEN-107 官方跑同为 192 文件 2298 项）——**计数零变化**，符合 Lead "不新增测试项、保持 2278/0/20" 的要求 |
| 外联尝试 | 仍 `attempts=6 unique_hosts=2`，逐条归属到 `tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip (setup)`，栈为 `knowledge_admin.py:247 ← knowledge_ingest.py:384 ← knowledge_ingest.py:191 ← embedding_provider.py:63`，全部被探针阻断、零出网、无计费。**本轮未改这个用例**——它属 QWEN-108 范围 |
| CI 口径 lint | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed**；`multi.py` 不在 mypy 白名单内，类型门无影响 |
| 裸 ruff（非 CI 口径，仅如实登记） | `test_manim_fallback.py` 42 → **49**（+7），`multi.py` 884 → **889**（+5），全部落在 `RUF001/RUF002/RUF003` 中文全角标点类，与 QWEN-107 同类，不在 CI 选择集内 |
| 抖动说明 | 定向从动上两轮的 277.40 s / 343.17 s 变为本轮 451.60 s，全量 1095.22 s → 756.16 s；本机媒体/模型链路未变，属既有 run-to-run 时长抖动，与本轮改动无因果证据 |
| 真链路（非 mock）交付验证 | `output/qwen107b-2026-10-22/probe_content_delivery.py` 一次运行：脚本态 `success=True` 且 `content` 为 **3002 字符** 的 `str`，`content == metadata.generated_code`；同轮日志第一手复现 Level-1 被质量门以 `drift=2.01s > 2.00s` 拒绝而脚本态仍成功。探针 `attempts=0 unique_hosts=0`（零出网）。日志 `logs/probe-content.txt`，详见 `docs/TEST_MATRIX.md` §9 |

## 13. QWEN-108 摄取用例显式离线登记（2026-10-22，分支 `qwen/wave1-manim`，零模型调用、产品代码零改动）

Lead 2026-10-22 裁定：`tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip` 的 embedding 调用是 QWEN-107 全量跑那 6 次外联尝试的来源，"探针挡住才绿，属测试依赖环境"；要求显式 offline/mock（`embedding_provider` 不可用或 monkeypatch），保留既有覆盖与断言，只改测试/fixture/文档，不改产品。

### 13.1 交付内容（1 个测试文件，+24 行）

| 位置 | 改动 |
|---|---|
| `tests/a/test_knowledge_platform.py:31-48` | 新增 **模块内 autouse** fixture `_offline_embedding_provider(monkeypatch)`：`monkeypatch.delenv` 清空 `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL`，使 `OpenAICompatibleEmbeddingProvider.available`（`backend/app/services/embedding_provider.py:36-38`）为 `False`，摄取走 `knowledge_ingest.py:205-206` 的 `not_configured` 离线路径 |
| `tests/a/test_knowledge_platform.py:227-233` | 在既有 roundtrip 用例末尾加一条**自检前提**断言 `get_embedding_provider().available is False`，使离线不只在探针日志里可见。**未新增 `def test_`**，既有条目与断言一项未删 |

### 13.2 未做的事（边界）

- **模块级 autouse 的代价与约束（Lead 2026-10-22 17:20 裁定保留）**：fixture 作用域覆盖该模块全部 14 个用例，模块内任何未来用例默认拿不到真 provider；若将来需要测"云端 embedding 已配置"的分支，**必须在用例内显式 `monkeypatch.setenv` 把三项 `EMBEDDING_*` 设回来**，不能依赖宿主环境。这条限制作为该模块的长期约束登记在此。

- **产品代码零改动**：QWEN-108 提交（`912d9b5`）相对 QWEN-107b 产品提交（`755454f`）在 `backend/` 下**零差异**（`git diff 755454f..912d9b5 --stat -- backend/` 实测为空），本轮唯一改动文件是 `tests/a/test_knowledge_platform.py`；`embedding_provider.py`、`knowledge_ingest.py`、`knowledge_admin.py` 均未动，路由仍 **189**（`grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l`）。
- **没碰 `.env`**：只用 `monkeypatch.delenv` 删除进程内环境变量，未读取、未打印、未提交任何值；文档里只写端点类别（embeddings），不写服务商。
- **没改 `ci.yml`**、没加 `|| true`、没装 `pywin32`、没动质量门阈值。
- **没扩到全仓**：只钉这个模块。QWEN-107 的 per-attempt 归属已证明全量 `distinct tests with outbound attempts=1`，即外联来源只有这一处，所以本卡完成后整套 `attempts=0`（实测见 13.3），无需再改其他文件。

### 13.3 本轮实测（证据等级：offline）

| 项 | 结果 |
|---|---|
| 定向 `tests/a/test_knowledge_platform.py`（per-attempt 探针） | **14 passed / 22.21 s**，`outbound attempts=0 unique_hosts=0`，`per-attempt attribution: 0 record(s)`，用例数与改动前相同 |
| 全量 `pytest tests/`（README 口径） | **2278 passed / 0 failed / 20 skipped / 764.23 s**，192 文件 / 2298 项 —— 计数与 QWEN-107/107b 逐项相同；**`outbound attempts=0 unique_hosts=0`、`distinct tests with outbound attempts=0`**（改动前同口径为 `attempts=6 unique_hosts=2`） |
| CI 便携清单（40 文件同清单） | **407 passed / 1 skipped / 0 failed / 77.83 s**，`attempts=0`，唯一 skip 仍是 `tests/a/test_auth_restart.py:18 Explicit disposable PostgreSQL required` |
| CI 口径 lint | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed** |
| 裸 ruff（非 CI 口径） | `tests/a/test_knowledge_platform.py` 15 → **30**（+15，全部 `RUF001/RUF002/RUF003` 中文全角标点类；`I001` 仍 1 条与 HEAD 相同），HEAD 对照在 `output/qwen108-2026-10-22/tmp/kp_head.py` |

### 13.4 过程中的两次实测纠错（如实登记）

1. **第一版断言写错位置**：我加了 `document["embedding"] == {"status": "not_configured"}`，定向跑 **1 failed / 13 passed，`KeyError: 'embedding'`**（`tests/a/test_knowledge_platform.py:231`）。核对后确认 `knowledge_ingest.py:243-248` 的 `"embedding"` 键属于 `_persist_enterprise_version` 的返回，不在 `ingest_document` 最终给 API 的文档 dict 里。改为断言 provider 的 `available is False`（前提条件，而非不存在的返回字段），随后 **14 passed**。日志：`output/qwen108-2026-10-22/logs/kp-targeted.txt`（失败轮）与 `logs/kp-targeted2.txt`（通过轮）。
2. **同轮 `attempts=0` 早在失败那次就已观测到**：失败轮探针已显示 `outbound attempts=0`，说明离线化生效、失败的只是我那条越界断言——两者没有因果混淆，故未把"绿"当成"离线"的证据。

## 14. QWEN-105 企业契约子集本机 PG 复跑登记（2026-10-22，分支 `qwen/wave1-pg`，零模型调用、产品代码零改动）

Lead 2026-10-22 裁定：用本机**已存在**的 `pgvector/pgvector:pg16` 与 `redis:7-alpine` 镜像（「直接使用，不要 pull」），起一次性环回容器跑企业契约子集（点名检查点跨进程恢复、部分完成 PG 恢复），记录真实 passed/failed/skipped 与命令、镜像 tag、耗时，只删自己的容器。

**本节证据等级：`pg`**（本机一次性容器第一手实测）。不是 `remote`，不是 Lead 转述，也不是之前 README 里那个来源不可追的「15/15」。

### 14.1 核心数字

| 轮次 | 结果 | 耗时 | 外联探针 |
|---|---|---|---|
| run1（URL 写 `localhost`） | 349 passed / **10 failed / 12 errors** / 0 skipped | 1698.19 s | `attempts=0` |
| run2（URL 改 `127.0.0.1`） | **364 passed / 0 failed / 0 skipped** | 162.58 s | `attempts=0 unique_hosts=0` |
| run3（run2 复跑确定性） | **364 passed / 0 failed / 0 skipped** | 159.53 s | `attempts=0` |

清单是 CI `enterprise-contract` job 的 **38 个文件**，由 `sed -n '297,336p' .github/workflows/ci.yml | grep -oE "tests/a/test_[a-z0-9_]+\.py"` 机械提取（`output/qwen105-2026-10-22/enterprise-list.txt`），未手工增删。

### 14.2 run1 的 10+12 已定位，不是产品缺陷（如实保留原样）

失败面全部集中在跨进程恢复类用例，报错类型是 `tests/a/test_postgres_api_recovery.py:13-18` 的 60 s **子进程超时**，不是断言失败。根因经实测复现：本机对 `localhost:55432` 每次建连耗时 **5.02 s**（Windows 先试 IPv6 再回落到 127.0.0.1），`127.0.0.1:55432` 仅 **0.01 s**；该文件的 `probe()` 每个阶段新起一个子进程连库，超时被建连延迟吃光。改 `127.0.0.1` 后同一批 5 个文件单独复验 **16 passed / 116.83 s**，随后 38 文件全量两轮 364 passed。CI 跑在 Linux runner 上不存在这段延迟，故这是**本机端口转发口径问题**，我按 Lead 要求把失败轮和根因都留着，没有只报干净的那轮。

### 14.3 真打在容器库上的旁证（清理前从宿主机查同一实例）

`tables=36`、`chunk_vectors=1372`、`knowledge_chunks=1372`、`checkpoint_migrations=10`、`alembic_version=1`；业务表 0 行是用例 `finally` 自行清理的结果。迁移照 CI 口径 `alembic upgrade head` 到 `20261014_0011`（11 个 revision），`pg_extension` 断言 `('vector',)` 通过。

### 14.4 Redis 的诚实边界（不把"服务可用"写成"用例已通过"）

Redis 容器就绪、`PING`/`SET`/`GET` 从宿主机往返成功，也被配成 `REDIS_URL` 与 Celery broker，但**这 38 个文件没有走真实 Redis 代码路径**：跑完 `dbsize=0`，子集内唯一引用 redis 的 `tests/a/test_v2_eval_cost_guard.py:17-22` 用 `FakeRedis` + `monkeypatch.setitem(sys.modules, "redis", ...)` 打桩。真 Redis 路径在 `tests/helpers/celery_ingestion_worker_probe.py:26`，属另一张卡，等 Lead 定。**故本卡的"企业契约子集通过"只主张 PG 层，不主张 Redis 层。**

### 14.5 与 CI 的口径差异（四条，全部列明）

1. `localhost` → `127.0.0.1`，5432/6379 → **55432/56379**（避开既有 `echomind-redis` 与共享 `triple-u-postgres`；见 14.2 根因）。
2. 额外 `-o addopts=`（本机 addopts 含 cov 组合）与额外 `LLM_PROVIDER=none`（CI 不设，我按零模型纪律加）。
3. 额外挂 `-p sandbox_tmpdir_shim -p qwen_net_probe` 以证明零出网。
4. **未跑** CI `ci.yml:338-341` 的可选 MCP stdio 步骤（需 `pip install -r requirements-mcp.txt`，本机未装，我没擅自装包）。

### 14.6 未做的事（边界）

- **产品代码零改动**：本卡只新增 `output/` 证据与文档登记；`git diff a505b21..HEAD --stat` 只落在 `docs/`。镜像**未 pull**（`docker image inspect` 确认两者本机已存在，ID `7b822b0aac60` / `858f009f9709`）。
- **容器隔离与清理**：容器名 `qwen105-pg-20261022` / `qwen105-redis-20261022`，端口只绑 `127.0.0.1`，`docker rm -f` 只针对这两个名字。`docker ps -a` 快照 18 → **16**，`qwen105-*` 计数 0；逐个 diff 非本卡容器，唯一差异是 `a3-backend` 的 uptime 文本，即其自行重启（**RestartCount=537**，策略 `unless-stopped`，日志 `failed to resolve host 'postgres'`，因共享 compose postgres 已 Exited 10 天）——**与本卡无关，我未对它执行任何 docker 子命令**，只登记。`echomind-*` / `a3-*` / `devtrace-*` 全部未动。
- **没读 `.env`**：口令是照抄 `ci.yml:245-247 / 265-269` 的 CI-only 占位值，用于已删除的一次性容器；`.env` 未读取、未打印、未提交。
- **零模型/零付费调用**：三轮全量 + 16 项复验的探针均 `attempts=0`，无任何出网字节。
- **未改 `ci.yml`**、未加 `|| true`、未新增/删除测试文件。

## 15. QWEN-107c 脚本态审计交付正文（2026-10-22，分支 `qwen/wave1-content`，零模型调用）

Lead 2026-10-22 18:40 裁定：脚本态成功时 `content` 已是 `metadata.generated_code`，但 `_enrich_with_safety_cov` 仍在 `multi.py:2807` 用**空的顶层 content** 计算 cov/safety，交付正文没经过审计；要求 enrichment 输入改为实际交付正文，`include_manim=true` 渲染分支保持原有 enrichment 语义，扩既有用例捕获审计输入，**不新增测试项**。

### 15.1 改动（2 个文件，+24 行，产品 +6 / 测试 +18）

| 位置 | 改动 |
|---|---|
| `backend/app/api/v1/artifacts/multi.py:2889-2894` | 脚本态成功分支在返回前用**交付正文**重算 enrichment（调用在 `:2892-2894`）：`enrichment = _enrich_with_safety_cov(script, req.kp_id or "", req.bloom_level or "", req.misconception or "", "manim")`，`script` 即 107b 交付给 `content` 的 `metadata["generated_code"]` |
| `tests/integration/test_manim_fallback.py:306-314 / 330-335 / 345-347` | 在既有 `test_script_only_is_success_when_render_not_requested` 内加 `_enrich_with_safety_cov` 记录型 spy（委托真函数，cov/safety 数值仍是产品自己算的），断言脚本态审计输入含讲稿正文；失败分支追加"空白伪正文不得进入审计"断言。**未新增 `def test_`** |

### 15.2 实现口径的选择（如实登记，非越界）

Lead 的字面要求是"输入改为顶层 `content` 或 `metadata.generated_code`"，同时又要求"渲染分支保持原有 enrichment 语义"。本 Level-2 路径里顶层 `content`（`r_dict["script"]/["code"]`）实际恒为空，若在 `:2807` 统一改成 `content or generated_code`，会连带把**已渲染出 MP4 的分支**的审计输入也从 `""` 变成讲稿正文，与第二条约束冲突。因此实现落在**脚本态成功分支内部**重算——该分支的交付正文按构造就是 `script`，渲染分支/质量门拒绝分支/讲稿缺失分支的 enrichment 输入逐字节不变。附带事实：脚本态成功时现在会调用 `_enrich_with_safety_cov` **两次**（`:2807` 的空文本一次、交付正文一次），前者结果在该分支不再被使用；这是为守住"不改渲染分支"而接受的冗余计算，未为此重构控制流。

另：本卡给 `multi.py` 增加 6 行（插入点在 `:2889`），`:2889` 之后的行号整体 **+6**——§12.1 记录的脚本态分支 `:2870-2898` 现读作 `:2870-2904`（分支起点 `:2870`、`script = str(...)` 仍在 `:2877` 未变；`content=script` 由 `:2892` 变 `:2898`；`MANIM_SCRIPT_MISSING_ERROR` 常量在 `:2671`，不受影响），旧正文按不回填规则不改。

### 15.3 本轮实测（证据等级：offline）

| 项 | 结果 |
|---|---|
| 单用例（`-k test_script_only_is_success_when_render_not_requested`） | **1 passed / 5.89 s**，探针 `attempts=0`；日志 `logs/single-test-positive.txt` |
| **反向验证**（`git apply -R` 临时撤掉产品 6 行后重跑同一用例） | **1 failed / 3.44 s**，报错正是新增断言：`AssertionError: 脚本态交付正文未进入审计：['']` —— 证明该断言真的钉住行为，修复前审计输入只有空串；日志 `logs/single-test-negative.txt`，随后 `git apply` 恢复，`git diff --stat` 复核为 2 文件 +24 行 |
| 定向整文件（14 用例，**用例数与改动前一致**） | **14 passed / 270.02 s**，`outbound attempts=0 unique_hosts=0`，per-attempt 归属 0 条；日志 `logs/targeted-run2.txt` |
| 全量 `pytest tests/`（README 口径） | **2278 passed / 0 failed / 20 skipped / 649.18 s**，192 个测试文件 / 2298 项（2278+20，与 107/107b/108 逐项相同）；`outbound attempts=0 unique_hosts=0`；日志 `logs/full-suite.txt` |
| CI 便携清单（同 40 文件清单，本轮机械重取 `ci.yml:164-220`） | **407 passed / 1 skipped / 0 failed / 56.90 s**，`attempts=0`，唯一 skip 仍是 `tests/a/test_auth_restart.py:18`；日志 `logs/ci-portable.txt`、清单 `ci-portable-list.txt` |
| 真链路（非 monkeypatch，`probe_audit_input.py`） | 把 Level 1 钉为不可用（本机媒体链路这一轮真的渲染出了 MP4，走不到脚本态分支），其余全真：`success=True`、`video_status='script_only'`、`content len=3002`，**审计输入序列 `[(0, ''), (3002, '# Auto-generated by Mani…')]`**，`delivered_content_audited=True`；`cov` 现为 `{checked: True, score: 0.0, passed: False, missing_terms: […]}`。对照 107b 同参探针存档（`output/qwen107b-2026-10-22/logs/probe-content.txt`）：那时审计的是空文本，`cov` 却给出 `{score: 1.0, passed: True}` 的**空文本虚过**。探针 `attempts=0 unique_hosts=0`；日志 `logs/probe-audit-input2.txt`（第一次未钉 Level 1 的运行留在 `logs/probe-audit-input.txt`，如实保留） |
| CI 口径 lint | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed**；`git diff --check` 干净；`multi.py` 不在 mypy 白名单 |
| 裸 ruff（非 CI 口径） | `test_manim_fallback.py` 49 → **54**（RUF003 +4 / RUF001 +1），`multi.py` 889 → **893**（RUF003 +4），全为中文全角标点类，不在 CI 选择集；基线副本在 `tmp/lintbase/` |
| 口径复核 | 路由装饰器仍 **189**、`git ls-files 'tests/**test_*.py'` 仍 **192**、`git diff --numstat` 只有 `multi.py` +6 与测试文件 +18 |
| 末次措辞改动后的复验 | 上面各轮跑完后，我只改了 `multi.py` 那 3 行注释的措辞（"上面的 enrichment 口径" → ":2807 的口径"，纯注释、无语义变化）。改后重跑：CI 口径 ruff **All checks passed**、裸 ruff `multi.py` 仍 **893**、同一单用例 **1 passed / 7.62 s** 且 `attempts=0`（`logs/single-test-final.txt`）。全量 2278/0/20 未为此重跑，按"注释不参与执行路径"判断沿用上一轮实测 |

### 15.4 影响面核查（不改红绿、不改兜底）

`_detect_manim_needs_fallback` 只看 `envelope.success` 与质量门，不读 cov/safety（`multi_with_fallback.py:56-68`）；`backend/app/agents/resource_generator_agent.py:131` 只把 `cov` 透传进 metadata。所以脚本态的 `cov.passed` 由"空文本虚过 `True`"变成"真正文可能 `False`"不会翻转 `success`、不会触发兜底、不改变前端媒体卡判定——14 用例与全量 2278/0/20 逐项不变就是这条的实测支撑。

### 15.5 过程中的两次自我纠错（如实登记）

1. 第一版在失败分支加了"该轮所有新审计输入必须为空"的断言，定向跑 **1 failed / 13 passed / 276.58 s**（`test_manim_fallback.py:345`）。前提写错了：`types=["manim"]` 的 rich 端点在 manim 失败后仍会生成 mindmap/tts 兜底资源，它们各自调用 `_enrich_with_safety_cov` 传的是自己的正文，与被测分支无关。改为精确断言"`"   "` 这个空白伪正文不得出现在审计输入里"后转绿。日志 `logs/targeted-run1.txt`。
2. 真链路探针第一次运行没钉 Level 1，本机媒体链路**真的产出了 MP4**，于是走的是渲染分支（`video_status='ready'`），脚本态分支根本没被走到；该运行没有证据价值，已如实存档为 `logs/probe-audit-input.txt`，第二次才补上 Level-1 不可用的钉桩。

### 15.6 本卡收口的旧登记（旧正文不回改，指向本节）

- §12.2（QWEN-107b 的未修披露）"`evidence`/`cov`/`safety` 的输入未动……CoV/Safety 校验的对象**不是**新交付的讲稿正文……若要'对交付的讲稿做安全/一致性校验'，需另开卡裁定"——**已由 Lead 18:40 开卡（QWEN-107c）并按本节实施**，该行文字按不回填原则保留为当时状态。
- §14 之后交接给 Lead 的三项待定中，本卡解决第一项；`ci.yml:338-341` 可选 MCP stdio 步骤仍未在本机跑（未擅自 `pip install`），README 的 `PostgreSQL 专项 15/15` 已按你 18:40 的裁定保留历史口径。

## 16. QWEN-109 评测用量/成本只读汇总（2026-10-22，分支 `qwen/wave1-evalcost`，零模型调用、产品代码零改动）

Lead 2026-10-22 23:05 开卡：数据源为评测产物 `runs.jsonl` 的 `budget`，**只读汇总**每臂/每题的调用数、输入/输出 token、latency、cost；`unknown` 不写 0、缺失样本单列计数；不编造单价、不读 `.env`；形式为脚本 + 脱敏报告，不新增对外端点、不改产品。

### 16.1 交付物（2 个新文件，均为新增，未改任何既有产品/测试代码）

| 文件 | 说明 |
|---|---|
| `scripts/report_eval_cost.py`（新增 461 行） | 只读聚合器。**不 `import os`**（结构上无法读环境变量或 `.env`）；不套用任何单价；`--out` 强制落在 `output/` 下且拒绝覆盖已存在文件；`--source LABEL=PATH` 可限定来源，缺省则扫描 `--scan-root`（默认 `output/`）并按"路径组件以 `test_` 开头"整份排除 pytest 夹具 |
| `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md`（新增 257 行） | 脱敏报告，与 `output/qwen109-2026-10-22/eval-cost-report.md` **逐字节相同**（`cmp` 通过）。报告首屏即写明生成命令、数据来源、样本量与未知项 |

记账口径**不自己另写一套**：每条记录经产品代码 `backend/app/services/run_usage.py` 的 `summarize_run_usage` 投影、按组交给 `aggregate_run_usage` 聚合（该模块只 `import typing`，无重依赖，实测可离线导入）。`cost_status` / `usage_status` / `runs_without_token_data` / `runs_without_estimated_cost` / `cost.reason` 全部是产品自己的词汇，与 §10.2 登记的口径一致。

### 16.2 实测汇总（证据等级：offline；对本机既有产物的只读再汇总，无任何模型调用）

样本：**8 份真实评测产物 / 127 条记录**；扫描根 `output/` 下含 `result.budget` 的 `.jsonl` 共 **130 份**，排除 pytest 夹具 **122 份 / 304 条记录**（排除规则与逐目录计数写进报告第 1 节）。

| 维度 | 实测 |
|---|---|
| 调用数合计 | **442**（127/127 条有值） |
| 输入 token 合计 | **1321838**（126/127 条有值） |
| 输出 token 合计 | **276031**（126/127 条有值） |
| input_chars 合计 | **2797092**（127/127） |
| latency_ms | 中位数 **14101.54**，区间 **2302.41~40332.14**（127/127） |
| cost | `cost_status: unknown×127`、`estimated×0`；**金额一律显示"未记录"**，无 estimated 成本 127 条 |
| usage_status | `measured×126, unknown×1` |
| 分组 | 每臂 **14** 个（来源×臂）组合；每题 **127** 行明细 |

三臂对照（`output/ablation-full-20261017/runs.jsonl`，各 24 题、模型 `deepseek-flash`；`completed=True` 数 / 调用数合计 / 输入 / 输出 token / latency 中位数）：`single` **23** / **24** / 76613 / 23866 / **5803.27 ms**；`without_reviewer` **13** / **86** / 234392 / 57479 / **15912.39 ms**；`full` **13** / **119** / 389382 / 72926 / **21411.53 ms**。调用量与 token 量按约 **1 : 3.6 : 5.0** 递增——这是本次汇总里唯一可支撑的跨臂结论，**不含质量判断**（质量通过率在原始记录里为空，本卡不重算、不代填）。

### 16.3 未知项与缺失样本（单列计数，一律不补 0）

- **成本维度 127/127 全为 `unknown`**：其中 `cost.reason=no_cost_amount_recorded` **126** 条、`cost_not_recorded` **1** 条（`single/ab-019`，`completed=False`，budget 里只有 `input_chars`/`model_calls`/`output_token_limit`，token 与 `cost` 对象都不存在）；`amount_cny`、`measured_portion_cny`、顶层 `cost_cny` 有值均为 **0** 条。因此报告不给任何折算金额，`unknown` 也不写成 0 元。
- 无 token 数据 **1** 条（同上），按产品聚合器口径**不参与 token 求和**；`usage_unknown_calls` 合计 **0**。
- `arm` / `config.model` 未标注 **36** 条：`retry-development-20261017.jsonl` 与两份 `stability-20261018` 复测产物的顶层 schema 更窄（只有 `case_id`/`evidence_sha256`/`result`[+`traces`]），latency 与调用数只在 `result` 下——报告按组显示为 `未标注`，不猜臂别。
- `result.error` 有值 **28** 条（运行本身失败，token 可能不完整），已在报告第 2 节单列。
- **跨来源合计只是记录求和，不是去重题数**：25 个题号出现在多个来源（如 `ab-001`~`ab-012` 同时出现在 ablation-full、retry-development、dev-retest），且各来源 `dataset_sha256` 不同或缺失，所以合计只能当**调用量上界**，不能当作一次评测的结果。报告第 5 节明写这条警告。

### 16.4 登记的产品侧观察（只登记，本卡不改产品代码）

`run_usage.py:22-26` 的 `_count` **只接受非负整数**（docstring 即"Accept only a real non-negative integer"），而评测记录里的 `result.latency_ms` 是小数，于是 `summarize_run_usage` 对这 **127/127** 条全部返回 `reported_latency_ms=None`（`model_calls` 因记成整数，实测被丢弃 **0** 条）。影响：任何直接消费该投影的用量视图都会把延迟显示成"未记录"。本卡的处理是**报告改为直接读原始 `result.latency_ms`**，并在报告首屏与第 2 节单列该偏差条数（127），未修改 `run_usage.py`。**归属：QWEN-104（成本/用量可见性）**，是否放宽 `_count` 或另存整数毫秒由 Lead 裁定。

### 16.5 自我校验（不用脚本自证）

| 校验 | 结果 |
|---|---|
| **独立复算**（`output/qwen109-2026-10-22/crosscheck_independent.py`，刻意不复用产品模块/聚合器/发现规则，走另一条代码路径） | 127 / 442 / 1321838 / 276031 / 2797092 / 有 token 126 无 1 / `result.error` 28 / 跨来源题号 25 / 14 个来源×臂组合，**14 行每臂数字逐行一致**；`logs/crosscheck.txt` 把两侧数字并排留档 |
| 与已接受结论交叉验证 ①（§2 的 **E3** 行 / `evals/results/ablation-fixed-evidence-20261017.md`，cloud 级） | 该表"任务完成 **23/24、13/24、13/24**" = 本汇总实测 `completed=True` **single 23 / without_reviewer 13 / full 13**；"平均模型调用 **1.00 / 3.58 / 4.96**" = 本汇总调用数合计 **24 / 86 / 119 ÷ 24 题**；"P50 耗时 **5.80 / 15.91 / 21.41 秒**" = 本汇总 latency 中位数 **5803.27 / 15912.39 / 21411.53 ms**；该文档正文"有 **1** 次运行缺少 token 用量" = 本汇总 `runs_without_token_data` **1**；"费用为**未知**" = `cost_status unknown×127`。**逐项一致**。该表的 P95（7.20 / 24.54 / 35.35 秒）本报告未计算（分位数方法不同，本卡不需要），但三者都落在我实测的 max（8542.39 / 25447.86 / 40332.14 ms）之内，不矛盾 |
| 与已接受结论交叉验证 ②（§2 的 **E5** 行 / `structured-output-20261018.md`） | 该行"**44/43** 次调用；输出 **25,384/25,286** tokens"与本汇总 `stability-20261018/dev-retest` **44 / 25384**、`holdout-retest` **43 / 25286** 完全一致 |
| 计数口径差异说明 | 独立复算报"cost unknown 126 + cost 对象缺失 1"，报告报"cost_status unknown 127"；两者不矛盾：产品 `_cost_of` 把缺失的 cost 对象**归为 `unknown` 且带 `reason=cost_not_recorded`**，报告第 2 节把该 1 条单列 |
| CLI 分支与错误路径 | `--source` 限定单来源 → 12 条 / 1 臂（排除清单仍报 122 份）；`--out` 不在 `output/` 下、`--out` 已存在、`--source` 缺 `=`、`--source` 路径不存在 → **均 exit 2 且不写出任何文件**；`logs/cli-branches.txt` |
| 零外联 | 复用 QWEN-106/107 的 fail-closed 探针（副本 `output/qwen109-2026-10-22/qwen_net_probe.py`）包住整次运行：`outbound attempts=0 unique_hosts=0`；最终版 `logs/run6-reproducibility.txt`（前几轮 `logs/run1~run5`） |
| **可复现性**（提交前的最后一道核对） | 把已交付报告挪到 `tmp/eval-cost-report-run5-final.md` 后，用**待提交的同一份脚本**在同一路径重新生成一次（同样套探针）：`sources=8 records=127 arms=14 cases=127 cost_status=unknownx127 runs_without_token_data=1 excluded_fixtures=122` 与 run5 逐字段相同，`cmp` 三方（run5 存档 / 重新生成 / `docs/` 里的脱敏副本）**全部逐字节相同**，探针仍 `attempts=0 unique_hosts=0`。脚本不含任何时间戳/随机源（未 `import` `datetime`/`time`），故输出确定。日志 `logs/run6-reproducibility.txt` |
| lint | CI 口径 `ruff check --select=F821,F823,E9 scripts/` → **All checks passed**；裸 ruff（`pyproject` 全集）对新文件 → **All checks passed / 0 findings**（未给 `scripts/` 既有 2382 条基线再添）；`git diff --check` 干净 |
| 脱敏复核 | 对报告全文 grep `sk-`/`api_key`/`bearer`/`password`/`secret`/URL/32 位以上十六进制/`deepseek.com` → **仅命中我自己那句"不读取 .env"**；出现的只有模型名 `deepseek-flash`、路径与计数；`dataset_sha256`/`evidence_sha256` 取值一律不复现 |

### 16.6 边界（未做的事，如实登记）

- **不新增测试项、未重跑全量**：本卡只新增 1 个脚本 + 1 份文档，未改任何产品/测试代码，新脚本不被任何测试 `import`，也无用例枚举 `scripts/` 或 `docs/`（全仓核查：`tests/a/test_human_eval_toolkit.py:7` 只导入 `scripts.human_eval` 包，其 `:111-113` 枚举的是 `tmp_path`；`tests/a/test_campus_assets.py:9` 枚举 `frontend/public/integrated-map/assets`；`tests/a/test_diagnosis_reporter.py:293` 枚举 `tmp_path`；无用例扫描 markdown 文档，`tests/b/test_contract_document.py:9` 只断言 `docs/API-CONTRACT.md` 存在）。故 README 的 **2278 / 0 / 20** 口径按构造不变；按"已交付数字不为好看而重跑"的既定约束未重跑全量，覆盖 `scripts/` 的 CI lint 门已在本机跑过并通过。
- **成本无法折算**：没有任何单价来源（环境变量未配置、记录里无金额），报告不给金额；若 Lead 要金额，需要先授权单价来源，届时 `cost.status` 会变成 `estimated` 而由产品自己算。
- **未新增端点、未改产品**：`git status` 仅 2 个未跟踪新文件；`backend/`、`tests/`、`ci.yml`、README 均未改动。
- 迭代过程产物按不删原则留档在 `output/qwen109-2026-10-22/tmp/`：`report_eval_cost-v1-parallel-accounting.py`（v1 自写一套成本判定，已弃用）、`eval-cost-report-run1-buggy-grouping.md`（排除清单归并键错写成 `output/...`）、`eval-cost-report-v1-parallel-accounting.md`、`eval-cost-report-v2-latency-lost.md`（改走产品投影后 latency 全部丢失的中间版，即 §16.4 的发现来源）、`eval-cost-report-v3-no-completed-column.md`（补 `completed` 列之前）、`eval-cost-qwen102-main-only.md`（`--source` 分支验证）、`eval-cost-report-run5-final.md`（重新生成前的已交付副本，供 run6 逐字节比对）。日志 `logs/run1~run4`（迭代过程）、`logs/run5-final.txt`（交付数字来源）、`logs/run6-reproducibility.txt`（提交前复现核对）、`logs/cli-branches.txt`、`logs/crosscheck.txt`。
- run5 之后对脚本做过一次**纯删死代码**的收尾：删掉 `Bucket.cases` 及其两行赋值（题号分组用的是 `main()` 里的 `per_case` 键，`Bucket` 内那份集合从未被读取）。删后两个 lint 门复跑仍 All checks passed，报告按 §16.5 的可复现性一行重新生成并逐字节相同——**未改动任何交付数字**。

## 17. QWEN-104b 延迟投影修复（2026-10-23，分支 `qwen/wave1-latency`，零模型调用）

Lead 2026-10-23 12:20 派卡、12:26 `[PERMISSION]` 放行（分支由 Lead 从 `main@dcaf082` 预建），固定决定见 §3-47：`reported_latency_ms` 用**独立的非负数值投影**（int/float 均接受，bool/负数/字符串/None 拒绝），而 **token、`model_calls`、`tool_calls` 等计数仍必须整数，不得放宽**；补 int/float/负数/bool/字符串测试，并验证管理端响应确实返回浮点延迟。本节即 §16.4 登记的产品侧观察的落地，**该观察由本卡关闭**。

### 17.1 改动（2 文件，+46/−2；产品 +8/−1，测试 +38/−1）

| 文件 | 改动 |
|---|---|
| `backend/app/services/run_usage.py` | 新增 `_number(value) -> int \| float \| None`（`:29-33`）：非负 int/float **原样返回**，bool/字符串/None/负数 → `None`。`summarize_run_usage` 的 `reported_latency_ms` 由 `_count(...)` 改为 `_number(...)`（`:92`）。**`_count` 一字未动**，token（`:73-75`）、`duration_ms`（`:91`）、`model_calls`（`:93`）、`tool_calls`（`:94`）仍走整数投影 |
| `tests/a/test_run_usage_admin.py` | 用例 9 → **11**：`test_reported_latency_keeps_measured_floats_and_rejects_non_numbers`（一次列表响应里并排 6 条记录：`900` / `5803.27` / `-1` / `True` / `"900"` / `null`）、`test_counts_stay_integer_only_while_latency_gains_precision`（budget 里塞 `model_calls 3.0`、`actual_input_tokens 12.5`、`actual_output_tokens 1.0`、`usage_unknown_calls 0.5` → 全部 `None`、`usage_status="unknown"`，同一条记录的浮点延迟仍照实返回）。夹具 `add_run` 的 `latency_ms` 形参注解放宽为 `Any`（要能写入 bool/str/null） |

实现取舍（3 条，均可复核）：

1. **命名按 §3-47 的 `_number`**（§4 只写"独立的非负数值投影"，未指定名字，两处不冲突）。
2. **不复用既有 `_amount`**：`_amount` 会 `float(value)` 强制转换且服务于金额求和（`cost_cny_estimated_sum`）；延迟不参与求和，强转 float 会把整数延迟 `900` 改写成 `900.0`，等于动了 QWEN-104 已验收响应里的既有取值。`_number` **保留原类型**（int 进 int 出、float 进 float 出），既有 9 个用例的 `reported_latency_ms == 900` 断言与响应文本逐字不变。
3. **未加 `math.isfinite`**：唯一写入方是 `backend/app/evaluation/ablation_runner.py:100` 的 `round((time.perf_counter() - started) * 1000, 2)`，按构造有限；NaN 已被 `value >= 0` 判否拒绝。仓库里另有两处同类过滤带 `isfinite`（`golden_set.py:178-180`、`learning_package.py:263-266`），若 Lead 要对齐口径，加 1 行判断 + 1 条断言即可。

### 17.2 实测（证据等级 offline；零模型调用、零外联）

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **11** 用例（原 9 + 新 2） | **11 passed / 1.34 s**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + fail-closed 探针（副本 `output/qwen104b-2026-10-23/qwen_net_probe.py`）→ `outbound attempts=0 unique_hosts=0`；日志 `output/qwen104b-2026-10-23/logs/targeted-run3-final.txt`；提交前用同一集合复跑 **11 passed / 1.33 s、`attempts=0`**（`logs/targeted-precommit.txt`） |
| **反向验证**（撤掉修复） | 同上 | 把 `:92` 临时改回 `_count(...)` → **2 failed / 9 passed / 1.67 s**，两处失败都是 `assert None == 5803.27`，即修复前浮点延迟确实被整条丢弃；随后改回并重跑转绿。**未用 `git apply -R`**（该命令被权限分类器拦截），改为一次编辑 + 改回，前后各跑 `git diff` 复核最终状态与预期一致；日志 `logs/targeted-negative.txt` |
| 管理端真实响应（`output/qwen104b-2026-10-23/probe_admin_response.py`，走 `TestClient` + 一次性 sqlite，非断言桩） | 2 条路由各 1 次 | `GET /api/v2/admin/run-usage/probe-run-1` → **200**，`reported_latency_ms` = **5803.27**（Python `float`），响应原文含 `"reported_latency_ms":5803.27`（**小数没有被截断成整数**）；列表路由同一记录同为 5803.27。同一条响应里 `model_calls 1` / `tool_calls 0` / `input_tokens 3715` / `output_tokens 878` / `usage_unknown_calls 0` / `duration_ms 1200` **仍是整数**；`cost_status="unknown"`、`cost.reason="no_cost_amount_recorded"`、`cost_cny=null`、`usage_status="measured"` 与 §10 的 QWEN-104 口径逐项一致；响应文本不含请求正文（`private`）。探针 `attempts=0 unique_hosts=0`。延迟取值取自真实评测记录（ablation-full `single` 臂的 latency 中位数）；日志 `logs/probe-admin-response.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9`（`ci.yml:115`）**All checks passed**；裸 ruff：`run_usage.py` **0 findings**，`test_run_usage_admin.py` **4 findings 与 HEAD 基线逐条相同**（3×E501 + 1×EM101，全是既有行、仅行号位移；基线副本 `output/qwen104b-2026-10-23/tmp/lintbase/`）；`git diff --check` 干净。路由装饰器仍 **189**（未新增端点） |
| 全量回归 | `pytest tests/`（2300 项） | **2280 passed / 0 failed / 20 skipped in 762.69 s**，口径与上一轮一致（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + 全新 `--basetemp output/qwen104b-2026-10-23/pytest-full`），探针 **`outbound attempts=0 unique_hosts=0`**，无计费模型端点、无用例因阻断转红；相对上一轮 2278 的 **+2 全部来自本卡新增的 2 个用例**，无既有用例转红或消失；日志 `logs/full-suite.txt` |
| CI 可移植子集 | `ci-portable-list.txt` 的 **40** 个文件（`diff` 与 107c 提取的清单逐行相同） | **409 passed / 1 skipped / 4 warnings in 56.07 s**，探针 `attempts=0 unique_hosts=0`；日志 `logs/ci-portable.txt`。子集口径与 §15 相同：只跑 CI 会在 Linux 上跑的测试文件 |
| 项数口径核对 | `--collect-only`（两次安静 + 一次非安静） | 安静收集两次输出 **逐字节相同**、各 **2299** 行（`tmp/collect-a.txt`、`tmp/collect-b.txt`）；非安静收集打印 `collected 2299 items / 1 skipped`（`logs/collect-verbose.txt`，8.75 s，探针同样 `attempts=0`）。那 1 条集合期跳过来自 `tests/a/test_mcp_readonly_protocol.py:11` 的 `importorskip("mcp")`（本机无 `mcp`，与 §15 登记的"CI MCP stdio 步骤本机未跑"同一原因），`torch` 本机可用故 `tests/b/test_sakt.py` 不跳。**2299 + 1 = 2300**，与运行时 2280 passed + 20 skipped 严格对齐；文档沿用运行时项数口径（上一轮 2298 = 2278 + 20），据此刷新 README 与导览 |

### 17.3 与既有登记的衔接（旧正文不回改，本节单向指认）

- **行号漂移**：`run_usage.py` 自原 `:29` 起整体 **+7**：新 `_number` 占 `:29-33`，`summarize_run_usage` 由 `:61` → `:68`，`aggregate_run_usage` 由 `:99` → `:106`，被改的调用点由 `:85` → `:92`。既有文档对本文件的引用只有 §16.4、矩阵 §13 与交付报告第 2 节的 `run_usage.py:22-26`（`_count`），**该行号未被本卡移动、无需换算**；`:85` 这个旧调用点此前没有任何正文引用过。§16/§10 里其它对该文件的行号推断如将来要用，按 +7 换算即可。
- **§16.4 关闭**：本节即该条产品侧观察的落地修复，观察项由本卡收口，不再另开卡。
- **QWEN-109 交付报告未被重新生成、未被改动**（Lead 边界「不改已合并结论」，且已验收数字不为"更好看"重跑）。为量化本卡对该报告偏差行的影响，改用**只写 scratch 的同命令复跑**：`output/qwen104b-2026-10-23/tmp/eval-cost-report-after-fix.md`（脚本本身拒绝覆盖已存在文件）。与 `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 的 `diff` 只有 **4 个 hunk / 6 行差异**（完整输出 `logs/eval-cost-delta.txt`）：
  1. 命令行 `--out` 路径不同（脚本把命令写进报告头，属必然差异）；
  2. 「与产品投影的偏差: latency_ms 有 **127** 条」→ **0 条**；
  3. 第 2 节同一行「latency_ms 被产品投影判为未记录 127」→ **0**；
  4. 夹具普查随轮次自然增长：含 `result.budget` 的 jsonl **130 → 138** 份、排除夹具 **122 → 130** 份 / **304 → 324** 条、归并表新增 `qwen104b-2026-10-23/... | 20`。
  **统计数字逐项不变**：127 条记录、8 个来源、调用数 442、输入 token 1321838、输出 token 276031、`input_chars` 2797092、latency 中位数 14101.54 [2302.41~40332.14]、`cost_status` 全 `unknown`、`runs_without_token_data=1`。夹具普查不是稳定数字（任何一轮的 `--basetemp` 都会往里加），已在 stdout 单列。
- **诚实登记的残留**：scratch 版里偏差行的**说明文字**仍是修复前的措辞（"小数 latency 全被丢弃 … 本卡不改产品代码"）。交付版按边界保持原样；若 Lead 认为需要更正文，只需改那 1 行说明，**任何数字都不动**。

### 17.4 边界（本卡没有做的事）

- 未向 `main` 提交或推送，只推 `qwen/wave1-latency`；未合并、未重启容器、未起本地服务。
- 零模型调用：本卡所有运行均挂 fail-closed 探针并记录 `outbound attempts=0 unique_hosts=0`（定向、反向、全量、CI 子集、管理端探针、集合核对共 6 次），计费端点一次都没出现。
- 未改端点语义与数量（仍 189 路由）、未改 `_count`、未改 `aggregate_run_usage`、未改 `cost`/`usage_status` 词汇与口径、未放宽任何计数为浮点。
- 未 `cat`、未提交、未上传 `.env`；本轮写入仓库的文件仅 §17.1 的两个代码/测试文件加 4 个文档（账本、矩阵、README、导览）。
- 未新增 `math.isfinite` 过滤（取舍见 §17.1 第 3 条，留给 Lead 裁定）；未重生成 QWEN-109 报告；未回改 §1-16 旧正文。

## 18. QWEN-104c `isfinite` 加固 + 报告措辞更正（2026-10-23，分支 `qwen/wave1-finite`，零模型调用）

Lead 2026-10-23 13:40 验收 §17（自行复跑 `test_run_usage_admin.py` **11 passed / 2.00 s**、全量 2280/0/20 接受、104b 已合并 `main`），并按 §17.1 第 3 条的裁定派本卡：(a) `_number` 与 `_amount` 加 `math.isfinite`（inf/-inf/nan → `None`，int/float 正常返回），补测试断言；(b) 更正 `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 里"latency 被投影判为未记录 127"的过期说明为"已由 QWEN-104b 修复、127→0"，**所有统计数字/结论不变**；(c) 零模型、只改投影/测试/文档。**§17.1 第 3 条留给 Lead 的裁定由本卡关闭。** 分支 `qwen/wave1-finite` 由 Lead 预建并推送；开工时工作树已被并发会话从 `main` 切到该分支（`git reflog` HEAD@{0}），无丢失改动、无 stash 条目。

### 18.1 改动（2 文件，+56/−3；产品 +4/−3，测试 +52/0）

| 文件 | 改动 |
|---|---|
| `backend/app/services/run_usage.py` | 新增 `import math`（`:11`）；`_number` 的判定改为 `math.isfinite(value) and value >= 0`（`:34`，docstring 同步为"finite non-negative"）、`_amount` 同一处理（`:40`）。**`_count` 一字未动**（整数不可能被 inf/nan 命中）。行号自 §17 起整体 **+1**：`_number` `:29-33`→`:30-35`、`_amount` `:36`→`:37`、`summarize_run_usage` `:68`→`:69`、调用点 `:92`→`:93`、`aggregate_run_usage` `:106`→`:107` |
| `tests/a/test_run_usage_admin.py` | 用例 11 → **13**：`test_non_finite_numbers_are_rejected_before_they_reach_the_wire`（直接对 `_number`/`_amount` 断言 `inf`/`-inf`/`nan` 三个取值全为 `None`，同时钉住 `900`/`5803.27`/`0.0042` 照旧通过；再把三条 inf/-inf/nan 延迟写入一次性 sqlite 走管理端，断言投影为 `null` 且响应正文不含字面 `Infinity`/`NaN`）、`test_non_finite_cost_amount_is_never_reported_as_money`（`amount_cny=inf` → `cost_cny=None`、`cost` 字典里**没有** `amount_cny` 键；`measured_portion_cny=nan` → `reason="no_cost_amount_recorded"`；聚合层 `cost_cny_estimated_sum=0`、`runs_without_estimated_cost=2`，即脏金额绝不进求和） |

### 18.2 为什么这道闸必须有（三条实测机制，不是纸面推断）

1. **漏网的只有 `+inf`**：撤掉守卫后 `_number(float("inf"))` 返回 `inf`（`value >= 0` 对 inf 为真），而 `-inf`/`nan` 本来就被 `>= 0` 判否。这与 §17.1 第 3 条"NaN 已被 `value >= 0` 拒绝"的结论一致，本卡补齐的正是 inf 那一支——所以不能只靠"上游按构造有限"。
2. **存储层不会替你挡住**：SQLAlchemy/SQLite 的 JSON 列**原样往返** inf。独立复跑实测 `metadata_data` 读回 `{"result": {"latency_ms": Infinity, ...}}`、`type(...)` 仍是 `float`、`.db` 文件里确有字面 `Infinity`（`NaN` 未出现，因为 `json.dumps` 对 nan 写 `NaN`、这条样本走的是 inf 分支）。脏值能一路走到投影输出。
3. **出接口的两层行为互相矛盾，更不能当保证**：同一份 summary，按 Starlette 的严格口径 `json.dumps(..., allow_nan=False)` 直接 **`ValueError: Out of range float values are not JSON compliant: inf`**（端点 500）；按 FastAPI/pydantic 的响应编码则把 inf **静默写成 `null`**——撤守卫跑测试时实测到 `cost` 出现 `amount_cny: None` 而 `cost_status` 仍是 `estimated`。前者是可用性故障，后者把"未记录"和"记成了 inf"混成同一个 `null`。因此按 Lead 决定把判定放在**投影层**，不赌构造有限、也不赌序列化器行为。

同类口径先例（§17.1 已列）：`golden_set.py:178-180`、`learning_package.py:263-266` 的过滤都带 `isfinite`，本卡后三处一致。

### 18.3 报告措辞更正（照 Lead (b) 执行，**未重生成报告**）

- 只改 2 行：第 1 节的偏差行、第 2 节偏差表行的说明列。两处都**保留 127 这个已交付实测值**，另标注"该说明已过期 / QWEN-104b 修复后复跑为 127→0"，未新增、未修改任何统计数字与结论。
- 与交付原件 `output/qwen109-2026-10-22/eval-cost-report.md`（gitignored）的 `diff` 现在正好是这 2 行（日志 `output/qwen104c-2026-10-23/logs/report-wording-delta.txt`）。**§16.5 的"三方逐字节相同"自此只对措辞更正前的版本成立**，旧正文不回改，指认本节。
- **未改 `scripts/report_eval_cost.py`**：那行说明的模板字符串硬编码在 `:380`（计数本身是算出来的，`projection_dropped["latency_ms"]` 现在会打印 0）。(c) 的范围是"只改投影/测试/文档"，脚本不在其中，所以我没动它——代价是**若将来重新生成报告，那行说明会再次变回旧措辞**。要不要一并改成 1 行字符串，请 Lead 裁定。

### 18.4 边界与如实登记

- 未向 `main` 提交或推送，只推 `qwen/wave1-finite`；未重启容器、未起服务、未跑任何付费模型调用；本卡所有运行均挂 fail-closed 探针。
- 未改 `_count`、未改任何计数口径、未改 `aggregate_run_usage` 的算法（只受 `_amount` 收紧的连带影响：非有限金额不再进入 `cost_cny_estimated_sum`，改由 `runs_without_estimated_cost` 计数）。
- 未 `cat`、未提交、未上传 `.env`；未新增端点（路由仍 **189**）；未回改 §1-17 旧正文。本轮写入仓库的文件仅 §18.1 的两个代码/测试文件加 5 个文档（账本、矩阵 §15、评测成本报告的 2 行措辞、README、导览）。
- **一处行为细节，钉在测试里但没有擅自"修"**：当运行记录里写的是 `cost.status="estimated"` 而 `amount_cny` 非有限时，投影**保留生产者写的 `estimated` 状态**、只把金额判为未记录，于是响应会出现 `cost_status="estimated"` 且 `cost_cny=null`（`cost` 字典不含 `amount_cny` 键）。若 Lead 认为这种情况应降级为 `unknown`，需要单独裁定——那会动到 QWEN-104 已验收的 `cost_status` 语义，本卡不越界。
- 越界发现：无新增。旧登记继续在册——`reports/` 未被 gitignore、17 个前端孤儿测试、`multi.py` 行号漂移、`scripts/` 裸 ruff 全角标点基线 2382 项、`scripts/report_eval_cost.py:380` 的过期解释模板（本卡已用复跑实证，见 §18.5 最后一行）。
- 并发会话：本卡开工时 HEAD 已由另一会话从 `main` 切到 `qwen/wave1-finite`（`git reflog` 可见 `checkout` 与 `merge ... Fast-forward` 记录）。我只登记这一现象与其证据，未尝试恢复、回退或评判任何不是我做的动作。

### 18.5 实测（证据等级 offline；零模型调用、零外联；Windows + Python 3.12.15）

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **13** 项（原 11 + 新 2） | 首跑 **13 passed / 2.44 s**、收尾复跑 **13 passed / 2.64 s**，两次探针均 `outbound attempts=0 unique_hosts=0`；日志 `logs/targeted-run1.txt`、`logs/targeted-final.txt` |
| **反向验证**（撤掉守卫） | 同上 13 项 | 临时把 `_number`/`_amount` 的 `math.isfinite(value) and value >= 0` 改回 `value >= 0` → **2 failed / 11 passed / 2.38 s**，两处失败分别是 `assert [inf, None, None] == [None, None, None]`（只有 `+inf` 漏网）与 `cost` 多出 `amount_cny: None`；改回后转绿。**未用 `git apply -R`**（该命令被权限分类器拦截），改为一次编辑 + 改回，前后各跑 `git diff` 复核，守卫版本另存 `tmp/run_usage.guarded.bak`、补丁 `tmp/finite-guard.patch`；日志 `logs/targeted-negative.txt` |
| 机制复测（支撑 §18.2 三条） | 独立脚本，非断言桩 | ① 无守卫时 `_number(inf)=inf`、`_number(-inf)=None`、`_number(nan)=None`，即漏网只有 `+inf`；② SQLAlchemy/SQLite JSON 列原样往返，读回 `latency_ms` 仍是 `float('inf')`，`.db` 文件里确有字面 `Infinity`（一次性夹具文件跑完即删）；③ 同一份 summary 按 Starlette 严格口径 `json.dumps(..., allow_nan=False)` 抛 `ValueError: Out of range float values are not JSON compliant: inf`，按 FastAPI/pydantic 响应编码则静默变 `null` |
| 全量回归 | `pytest tests/`（**2302** 项） | **2282 passed / 0 failed / 20 skipped / 873.67 s**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen104c-2026-10-23/pytest-full`，探针 **`attempts=0 unique_hosts=0`**；相对 104b 的 2280 恰好 +2 即本卡新增两项，既有用例无一转红；项数口径沿用 §17 的运行时算法：`--collect-only -q` 收 **2301** 项（14.81 s，探针 `attempts=0`）+ 集合期 1 条 `tests/a/test_mcp_readonly_protocol.py:11` 的 `importorskip("mcp")` skip = **2302 = 2282 + 20**，与 104b 的 2299+1=2300 同口径（日志 `logs/collect-quiet.txt`）；日志 `logs/full-suite.txt` |
| CI 可移植子集 | `ci-portable-list.txt` 的 **40** 个文件（与 107c/104b 清单 `diff` 相同） | **411 passed / 1 skipped / 4 warnings / 83.99 s**（上一轮 409/1，+2 即本卡两项），探针 `attempts=0 unique_hosts=0`；日志 `logs/ci-portable.txt` |
| 报告复跑（只写 scratch，**不改已交付报告**） | `python scripts/report_eval_cost.py --scan-root output --out output/qwen104c-2026-10-23/tmp/eval-cost-report-final.md` | stdout `sources=8 records=127 arms=14 cases=127 cost_status=unknownx127 runs_without_token_data=1 excluded_fixtures=138`；复跑产物第 9 行 `latency_ms 有 **0** 条被投影判为未记录`、第 79 行同为 **0** ——**§18.3 那句"复跑此计数为 127→0"在最终代码上成立**，不是推断。与已交付报告 `diff` = **6 hunk / 23 行**（`logs/report-rerun-delta.txt`），除命令行 `--out` 路径、这两处偏差值、夹具普查随轮次增长（含 `result.budget` 的 jsonl 130→146 份、排除夹具 122→138 份 / 304→344 条、归并表新增 104b/104c 两行各 20 条）之外**逐字节相同**：127 条记录、442 次调用、1321838/276031 token、2797092 `input_chars`、中位数 14101.54 [2302.41~40332.14]、`cost_status unknown×127` 全部不变 |
| 复跑暴露的模板自相矛盾（登记，未擅自修） | 复跑产物第 79 行 | 计数已算成 **0**，但同一行说明仍是硬编码的"`_count` 只接受非负整数, 小数 latency 全被丢弃 …… 本卡不改产品代码"（模板在 `scripts/report_eval_cost.py:380`）——旧解释与新数字并排，自相矛盾。这是 §18.3 请 Lead 裁定"要不要一并改这 1 行模板字符串"的实证；(c) 范围限定为投影/测试/文档，脚本不在其中，故本卡只登记 |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9` **All checks passed**；裸 ruff：`run_usage.py` **0 findings**，`test_run_usage_admin.py` **4 findings 与 HEAD 基线逐条相同**（3×E501 + 1×EM101，行号 `35/107/173/241` → `36/108/174/293`，基线副本 `tmp/baseline_test.py`）；`git diff --check` 干净；路由装饰器仍 **189**、测试文件仍 **192** |


## 19. QWEN-104d 两项裁定的落地 + 报告模板旧说明修正（2026-10-23，分支 `qwen/wave1-finite`，零模型调用）

Lead 2026-10-23 16:05 验收 §18（自行复跑 `test_run_usage_admin.py` **13 passed / 2.30 s**、全量 2282/0/20 接受、104c 已合并 `main`），并把 §18 交回的两件裁定**全部批准**，落成小补丁 **QWEN-104d**（继续用 `qwen/wave1-finite`）：

1. **脚本模板旧说明**——原文「批准改 `scripts/report_eval_cost.py:380` 的硬编码字符串，改为"latency 已由 QWEN-104b/104c 修复、复跑 127→0"；**不重生成 tracked 报告**；用 scratch 复跑验证该行，并在台账注明模板已修。」（关闭 §18.3 的待定）
2. **`estimated` 但金额非有限/缺失**——原文「**保留生产者 `status="estimated"`，不降级**；在 `cost` 字典补 `reason="no_cost_amount_recorded"`，让"estimated 却无金额"不再含混；更新测试与台账。」（关闭 §18.4 的待定）
3. 零模型、只改脚本/投影/测试/文档；完成后 `[DONE]`。

Lead 同时确认 §18.4 报备的并发会话现象（HEAD 被切到 `qwen/wave1-finite`）是 Lead 自己预建分支/同步文档所致，不是异常、无需恢复——该登记就此关闭。

### 19.1 改动（3 文件，+46/−4；投影 +4/0，脚本 2/2，测试 +40/−2）

| 文件 | 改动 |
|---|---|
| `backend/app/services/run_usage.py` | `_cost_of` 新增一支 `elif status == ESTIMATED and amount is None: projected["reason"] = "no_cost_amount_recorded"`（`:66-69`）。**只补解释、不动状态**：`cost["status"]` 仍是生产者写的 `estimated`，`cost_cny` 仍是 `null`，聚合的 `runs_without_estimated_cost` 口径不变（它按 `cost_cny is not None` 过滤，与本支无关）。插入点在原 UNKNOWN 支之后，故 `summarize_run_usage` `:69`→`:73`、`reported_latency_ms` 调用点 `:93`→`:97`、`aggregate_run_usage` `:107`→`:111`（自 §18 起再 **+4** 行漂移） |
| `scripts/report_eval_cost.py` | `:381-382` 的硬编码说明由「`run_usage.py:22-26` 的 `_count` 只接受非负整数, 小数 latency 全被丢弃 ……（只登记, 本卡不改产品代码）」改为「已由 QWEN-104b/104c 修复: `_number` 现接受非负 int/float 并要求 math.isfinite, 复跑本计数 127 -> 0; 本报告仍按原始值读, 本行由产品投影实时算出」。**只改这一处模板**：下一行 `model_calls` 的「同一规则; 实测 0 条」照旧成立（`_count` 未动），未改；计数本身仍是 `total.projection_dropped["latency_ms"]` 实时算出 |
| `tests/a/test_run_usage_admin.py` | 用例 13 → **14**。① `test_non_finite_cost_amount_is_never_reported_as_money`（`:259`）的 `cost` 全等断言加上 `"reason": "no_cost_amount_recorded"`；② 新增 `test_estimated_status_without_a_usable_amount_explains_the_absence`（`:288-321`）把"estimated 但投影拿不到可用金额"的**五种形态**逐一钉住——**缺 `amount_cny` 键**、`None`、**负数 `-5`**、**字符串 `"0.0042"`**、**`True`（bool）**——都保留 `estimated` 并补 reason；对照组 `amount_cny=0.0025` 的 `cost` **不含 reason**；聚合层 `cost_status={"estimated":6,"unknown":0}`、`cost_cny_estimated_sum=0.0025`、`runs_without_estimated_cost=5` |

### 19.2 这次改的是什么语义（以及没改什么）

- **改**：`cost` 字典里"estimated 却没有金额"这一格从**沉默**变成**带原因**。此前 `reason` 只在 `status=unknown` 且金额与 portion 全无时出现，于是同一个响应可以出现"`cost_status=estimated`、`cost_cny=null`、`cost` 里没有任何解释"——读数的人只能猜是投影丢了金额还是生产者漏写。现在这类记录统一带 `no_cost_amount_recorded`，与 §7 既有的 unknown 解释复用同一个词，不新造枚举。
- **该 reason 的准确含义**（沿用 §7 既有口径，本卡不新造语义）：它说的是"**投影手上没有可用金额**"，不是"生产者一定没写"。`amount_cny` 缺键、为 `None`、非有限（inf/nan）、负数、字符串或 bool 都会走到这一支——后几种是生产者写了但被 `_amount` 判为不可用。这与原 UNKNOWN 支的 `no_cost_amount_recorded` 完全同口径（那里的判定同样来自 `_amount` 返回 `None`）。覆盖面：inf 在 `:259`（104c 已有），缺键/`None`/负数/字符串/bool 五种在本卡 `:288-321`。**一处自我更正要如实登记**：本节初稿把"负数/字符串/bool"写成"早在 §17 的 `:200`/`:220` 就钉住"，核对后发现那两条测的是 `_number`（延迟）与 `_count`（计数），**与金额路径无关**——该覆盖当时并不存在，于是本卡把它补进新用例，而不是留一句不实的引用。
- **没改**：`COST_STATUSES` 仍是 `(estimated, unknown)`；不降级、不推断、不补任何金额；`cost_cny` 仍只在 `estimated` 且金额可用时非空。§7 第 219 行「`cost_cny` **只在 `estimated` 时非空**」这一**方向**的口径继续成立；其逆命题本来就不成立，本卡只是把逆命题的反例显式标注出来，§7 旧正文不回改，指认本节。
- **没改**：`_count`/`_number`/`_amount` 三个投影函数、`aggregate_run_usage` 算法、端点与响应结构（`cost` 本就是自由字典，新增键不触及任何既有断言）。

### 19.3 实测（证据等级 offline；零模型调用、零外联；Windows + Python 3.12.15）

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **14** 项（原 13 + 新 1） | 两处产品改动落地后首跑 **14 passed / 1.84 s**（`logs/targeted-run1.txt`，15:57）；反向验证撤支、恢复守卫后的即时复跑 **14 passed / 1.59 s** 当时只打在终端、没有单独存档，因此本卡把**用例补全后**的 **14 passed / 2.64 s**（`logs/targeted-final.txt`，16:14 > 测试文件 16:04）作为最终代码的留档凭证；提交前再跑 **14 passed / 2.44 s**（`logs/targeted-precommit.txt`，文档改动全部落地后的状态）；三次日志末尾都是探针 `outbound attempts=0 unique_hosts=0` |
| **反向验证**（撤掉裁定 2 的新支） | 同上 14 项 | 把 `elif status == ESTIMATED and amount is None:` 临时改成永不为真（`and False`）→ **2 failed / 12 passed / 2.20 s**，两处失败都是 `cost` 字典缺 `reason` 键的全等断言（`{'status': 'estimated', 'currency': 'CNY'} != {...no_cost_amount_recorded}`）；改回后转绿，`git diff` 复核补丁存档 `tmp/reason-branch-disabled.patch`、`tmp/reason-branch.patch`。仍未用被权限分类器拦截的 `git apply -R`；日志 `logs/targeted-negative.txt` |
| 模板修正的验证（**不重生成 tracked 报告**） | 同命令只写 scratch | `python scripts/report_eval_cost.py --scan-root output --out output/qwen104d-2026-10-23/tmp/eval-cost-report-after-template.md` → stdout `sources=8 records=127 arms=14 cases=127 cost_status=unknownx127 runs_without_token_data=1`；复跑产物第 79 行现在是「`\| latency_ms 被产品投影判为未记录 \| 0 \| 已由 QWEN-104b/104c 修复: … 复跑本计数 127 -> 0; … \|`」——§18.5 登记的"计数 0 + 旧解释"自相矛盾行**消失**；统计口径与 104c 复跑一致（127 条记录、`cost_status unknown×127`）。日志 `logs/eval-cost-rerun.txt` |
| 全量回归（**最终代码，记录数**） | `pytest tests/`（**2303** 项 = `--collect-only -q` 收 **2302** 项 + 集合期 1 条 `tests/a/test_mcp_readonly_protocol.py:11` 的 `importorskip("mcp")` skip，与 104c 的 2301+1=2302、104b 的 2299+1=2300 同口径；收集用时 15.75 s，探针 `attempts=0`） | **2283 passed / 0 failed / 20 skipped / 842.46 s（14:02）**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen104d-2026-10-23/pytest-full-final`，探针 **`outbound attempts=0 unique_hosts=0`**、无用例因阻断转红；相对 104c 的 2282 恰好 **+1**，就是本卡新增的那一项，既有用例无一转红；日志 `logs/full-suite-final.log`、`logs/collect-quiet.txt` |
| 全量回归（用例补全前，只作过程记录） | 同命令、同项数 | 2283 passed / 20 skipped / **807.42 s**（`logs/full-suite.txt`，16:13 结束）。该轮起跑时测试文件还是 16:04 之前的初版（新用例只覆盖缺键与 `None` 两种形态，后续只在一个测试函数内部加断言，测试函数个数不变），项数与最终一致但**不作为本卡记录数** |
| CI 可移植子集 | `ci-portable-list.txt` 的 **40** 个文件（含 `tests/a/test_run_usage_admin.py`） | **412 passed / 1 skipped / 90.29 s**，`--basetemp output/qwen104d-2026-10-23/pytest-ci`，探针 `outbound attempts=0 unique_hosts=0`；相对 104c 的 411/1 恰好 +1，同为本卡新增项；quiet 输出无任何 `admin` 失败行（14 项全绿）；日志 `logs/ci-portable.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9` **All checks passed**；裸 ruff：`run_usage.py` **0 findings**、`report_eval_cost.py` 改动行不新增 finding（`scripts/` 全角标点基线不变），`test_run_usage_admin.py` 仍是 **4 findings**（3×E501 + 1×EM101，行号 `36/108/174` 不变、EM101 `293`→`331`），与 HEAD 基线（`git show HEAD:` 后单独 lint）逐条相同；路由装饰器仍 **189**、测试文件仍 **192**；`git diff --check` 干净 |

### 19.4 边界与如实登记

- 未向 `main` 提交或推送，只推 `qwen/wave1-finite`；零模型调用、零外联（所有运行挂 fail-closed 探针）；未 `cat`、未提交、未上传 `.env`；未新增端点；未起或重启服务。
- **tracked 报告未重生成**：`docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 本卡**一字未动**（Lead 明令），模板修正只作用于将来的生成物；验证一律写 scratch。
- 全仓消费方核查：`grep -rn '"cost"\|cost =='` 在 `tests/` 与 `backend/app/` 的命中只有 `tests/a/test_run_usage_admin.py` 的断言、`tests/a/test_v2_model_usage.py` 的 3 处（那是 `usage_meter` 写入的原始 budget，不经投影、不受本卡影响）与 `run_usage.py` 自身；`grep -rln report_eval_cost tests/` 为空，故脚本模板改动没有测试面。
- 越界发现：无新增。旧登记继续在册——`reports/` 未被 gitignore、17 个前端孤儿测试、`multi.py` 行号漂移、`scripts/` 裸 ruff 全角标点基线 2382 项、可选 MCP stdio 步骤（`ci.yml:338-341`）本机未跑。**§18.3 与 §18.4 两处"留给 Lead 裁定"由本卡关闭。**
## 20. QWEN-201 确认门控的长期记忆（2026-10-23，分支 `qwen/wave2-memory`，零模型调用）

Lead 2026-10-23 17:20 验收 §19（自行复跑 `test_run_usage_admin.py` **14 passed / 1.70 s**，104d 已合并 `main`），随即派 **QWEN-201** 并明令「现在开工（允许，不适用交付后 hold）」；分支由 Lead 预建并 fast-forward 到 `main@542d8be`，本轮开工 HEAD = `a312050`、工作树起点干净。派工四点原文：

1. `user_memories` + `memory_events` 迁移，**upgrade/downgrade 在隔离 SQLite 真跑并留日志**；
2. 模型只能 `propose`（不落库）；`confirm` 必须显式用户/教师 actor；`revoke` 留审计；TTL 过期不读；**同用户同 kind 去重策略写清**；
3. **partial/failed Run 永不入记忆**；未确认不落库；revoked 不可读；审计完整；
4. 零模型、不读 `.env`；不改 API/UI（留给 203）；更新 `CLAIMS_LEDGER`/`TEST_MATRIX`。整体完成后一次 `[DONE]`，附迁移回滚证据、测试数字、未做清单。

§3 的原始表设计另有两处约束被本轮当作硬口径执行：`source`「run_id/教师/用户显式」三种来源、以及「写入只允许**规则提取** + **用户确认或教师审核**，模型只能提议，不得自动写」。

### 20.1 改动（1 个文件扩展 + 4 个新文件，共 +725 行、删除 0 行）

| 文件 | 改动 |
|---|---|
| `backend/app/core/models.py` | **纯追加 +43/0**（`@@ -644,0 +645,43 @@`，落在 `:645-687`）：`UserMemoryRecord`（`:651`，表 `user_memories`）与 `MemoryEventRecord`（`:677`，表 `memory_events`）。列集逐字对齐 §3-51 与 §3 表设计：`id/user_id/kind/content/source_type/source_run_id/confidence/expires_at/status(active\|revoked)/created_at/updated_at` 与 `id/memory_id/action/actor/reason/created_at`。去重不写在服务层的口头承诺里，而是写进 schema——部分唯一索引 `uq_user_memory_active`（`:671-673`，`WHERE status = 'active'`，SQLite 与 PostgreSQL 各给一份方言）。审计表按仓库既有惯例**不带外键**（`memory_id` 只是普通索引引用，与 `debate_logs`/`retrieval_logs` 同族）。`__tablename__` 计数 **37 → 39**；裸 ruff 计数 **18 → 18**（与 `git show HEAD:` 基线逐条相同，本卡扩展零新增风格项） |
| `alembic/versions/20261023_0012_user_memories.py`（新，56 行） | `revision = "20261023_0012"`、`down_revision = "20261014_0011"`（新 head）。`upgrade()` 第一行就是 `if sa.inspect(op.get_bind()).has_table("user_memories"): return`——照抄 `20261010_0005` 的 `_ensure_knowledge_documents_table` 幂等写法，因为本仓 `init_db()` 走 `create_all`，应用先建过表时迁移必须识别并跳过（该分支由 `test_memory_migration_roundtrip[True]` 与 CLI 真跑双证）。建 2 表 + `user_memories` 5 个索引 + `memory_events` 2 个索引；`downgrade()` 逐表 `has_table` 后先 drop 索引再 drop 表。import 块与 `20261014_0011_login_attempts.py:2-4` 逐字同形 |
| `backend/app/services/user_memory.py`（新，270 行） | 五个入口：`propose`（`:108`）、`confirm`（`:141`）、`revoke`（`:199`）、`active_memories`（`:234`）、`memory_audit`（`:256`）。**`propose` 的签名里根本没有 session 参数**，"未确认不落库"因此是结构保证而非纪律；其余四个入口一律由调用方注入 `session_factory`（沿用 `backend/app/agent_runtime/conversation_memory.py:8` 与 `run_audit` 的既有可测口径）。绑定常量：`HUMAN_ACTOR_ROLES = ("student", "teacher")`（`:31`）、`MEMORY_ELIGIBLE_RUN_STATUS = "completed"`（`:35`）。错误面两类：`MemoryPolicyViolation`（`:41`）只给稳定 code（`source_run_not_completed`、`confirmation_requires_human_actor`、`ttl_must_be_positive`……），`MemoryPersistenceError`（`:45`）把任何未预期异常统一压成 `memory_persistence_unavailable`，不外泄 DB 文本——与 `run_usage.py` 的 `run_persistence_unavailable` 同族 |
| `tests/a/test_user_memory_service.py`（新，251 行 / **50 项**） | 逐项钉死写入策略：propose 零落库、未确认永不可读、confirm 落 1 行 + 1 条审计、`partially_completed`/`failed`/`awaiting_approval`/`reviewing`/`interrupted`/`rejected`/`running` **七态参数化**一律拒入记忆、来源 run 不存在即拒、actor 五形态（`agent`/`system`/`anonymous`/空串/`None`）参数化拒绝、非 proposal 拒绝确认、同 `(user, kind)` 转 `superseded`、异 kind 共存、跨用户不可读不可顶、revoked 不可读但审计在、重放 revoke 不灌水、过期不读但行不删、过期前驱的审计标签、confidence/TTL/形状各自的拒绝码、被篡改的 proposal 在 confirm 时重新校验、写失败不泄露 DB 文本 |
| `tests/a/test_user_memory_migration.py`（新，105 行 / **3 项**） | 在临时 SQLite 上直接驱动迁移对象：`[False, True]` 两态（空库、或先 `create_all` 模拟 `init_db()`）各做 **upgrade ×2 → 断表/列/索引 → 插入记忆与审计 → downgrade → 记忆表消失且无关表 `unrelated_probe` 的 7 行仍在 → 再 upgrade → 表回来且为空**；第三项钉住部分唯一索引只拦活行 |

### 20.2 这一层到底保证了什么（含三处需 Lead 追认的读法）

- **三段式写入**：`propose` 只在内存里成形，返回体带 `persisted: False`；`confirm` 是唯一落库路径，且要求 `proposal["record"] == "proposed"`，否则 `confirmation_requires_a_proposal`；`revoke` 只改状态、绝不删行，审计与内容都可继续读。§3「模型只能提议，不得自动写」由签名层保证——模型侧拿不到 `session_factory`。
- **运行资格闸门**：`_check_source_run`（`:131`）在**同一事务内**用 `session.get(AgentRunRecord, …)` 核对来源 run，`status != "completed"` 一律 `source_run_not_completed`。口径与既有实现完全对齐：`backend/app/agent_runtime/conversation_memory.py:16`（`status == "completed"`）加 `:19`（`metadata["memory_eligible"]`），以及 `backend/app/agent_runtime/run_audit.py:154` 把 `success_count` 定义成 `int(status == "completed")`。run 不存在时选**拒绝**而非静默丢弃（`source_run_not_found`）：默认丢弃会让一个拼错的 id 悄悄变成"没有来源的合法记忆"。
- **TTL 从确认时刻起算**，不从起草时刻：一条未确认的候选可以在管道里放任意久，冻结 `expires_at` 会让它一确认就已过期。`propose` 只带 `ttl_seconds`，`confirm` 才换算 `expires_at = now + ttl`。过期采取**只不读、不删**（`active_memories` 过滤 `expires_at IS NULL OR expires_at > now`），投影里显式给 `expired` 布尔；被顶掉的行若恰好已过期，审计 `reason` 记 `ttl_expired` 而非 `superseded_by:<id>`。
- **去重策略（Lead 点名要"写清"的一件）**：同一 `(user_id, kind)` **只允许一条 `active`**。两处表达——① schema 层部分唯一索引 `uq_user_memory_active`，`superseded`/`revoked` 的历史行不受约束，审计因此可无限累积而不撞库；② 服务层 `confirm` 在同一事务里锁定旧活行、置 `REVOKED` 并写 `SUPERSEDED` 事件，再插新行 + `CONFIRMED` 事件。于是"系统曾经相信什么、被谁顶掉的"永远可回放，而不是被一次 REPLACE 抹平。选**顶掉**而非**并存**或**报错**：§3 给 `kind`（偏好/目标/薄弱点）的定位是"同一维度的当前认知"，并存会让下游读到两条互斥的当前值，报错则使模型无法自我修正。SQLite 侧实测证据在 `logs/schema-smoke.txt`（撞索引 → `IntegrityError`；活行改 `revoked` → 槽位释放）。
- **人类 actor 的口径**：`confirm` 要求 `actor_role ∈ ("student", "teacher")`（`:31`），`admin`/`agent`/`system`/空串一律 `confirmation_requires_human_actor`。**三处读法需你追认，本卡按字面实现、一处都没擅自扩**：
  1. §3 原文「用户确认或教师审核」→ `student`（注册账号默认角色）与 `teacher`。`api/v2/access.py:99-103` 的 reviewer 集合 `{teacher, admin}` 管的是盲评权限，与"确认权"无关，本卡未借用。**`admin` 因此被拒**——若你认为管理员也应能确认，改动面只有这一个元组 + `test_confirm_requires_a_human_actor` 的参数表。
  2. 你只规定 `confirm` 要人类 actor，对 `revoke` 的原话是"留审计"。本卡把同样的守卫也加在 `revoke` 上（`revocation_requires_human_actor`），理由是"能写"与"能撤"的信任级若不对称，一个非人类 principal 就能既写入又抹除。**这是本卡的选择，不是你的原话。**
  3. §3 表设计里 `source` 列举了「run_id/教师/用户显式」三种来源。本卡落成 `source_type`（默认 `rule_extraction`，限长 32 的自由串）+ 可选 `source_run_id` 两列，**没有把来源写成闭集**：把三种来源收紧成白名单需要先裁定"教师直接 authored"与"规则提取候选"是否同权（若不同权，白名单还会改变 `confirm` 的闸门语义）。若你要闭集，改动面是 `_LIMITS` 旁加一个常量 + 一条参数化用例。
- **审计幂等**：对一条已退役的记忆重放 `revoke` 返回 `changed: False` 且**不写第二条事件**，避免重试或重放把审计灌水。

### 20.3 测量（全部离线口径，证据等级 offline）

| 项 | 结果 |
|---|---|
| **迁移真跑（隔离 SQLite，Lead 点名的回滚证据）** | `alembic` CLI，库只落在 `output/qwen201-2026-10-23/tmp/alembic-memory.db`：`heads` = `20261023_0012 (head)`；空库 `upgrade head` 跑满 **12** 个 revision → 34 张表含两张新表，DDL 原文取到 `CREATE UNIQUE INDEX uq_user_memory_active ON user_memories (user_id, kind) WHERE status = 'active'`；`downgrade base` 回滚 **12** 步 → **两张表与全部 7 个索引消失**、`alembic_version` 归空；**再 `upgrade head`** → 34 表回归、两张记忆表 0 行、`current` 仍是 head。`data/a3_learning.db` mtime `16:18:17` 早于本轮 `17:30:48–17:30:56` 窗口，未被写过；`DATABASE_URL` 由命令行显式给出、日志只记路径不记凭据，未读 `.env`。日志 `logs/migration-cli.txt`。**同轮第一次跑的检视片段自身取列出错**（单列查询按 `r[1]` 取 → `IndexError`），另存 `logs/migration-cli-run1-probe-bug.txt` 不删，属取数工具错、不改任何产品结论 |
| **CI 的 alembic smoke 同形复跑（`ci.yml:142-147`）** | 独立空库 `tmp/ci_smoke.db` 上 `python -m alembic upgrade head && python -m alembic downgrade base`：**exit=0 / exit=0**，12 步升级（含 `20261014_0011 -> 20261023_0012` 一行原文）+ 12 步回滚。日志 `logs/ci-alembic-smoke.txt`、`logs/ci-smoke-upgrade.txt`、`logs/ci-smoke-downgrade.txt` |
| **一条既有现象的取证（不属本卡，登记并归位）** | 若把两条路径混在**同一个库文件**上——先 `init_db()`（`create_all`）再 `alembic upgrade head`——则 `upgrade` 以 **exit=1** 失败于 `sqlite3.OperationalError: table profiles already exists`，即 baseline revision `20260618_0001` 的无条件 `create_table`。三条判据证明与本卡无关：① 失败日志里 `20261023_0012` 出现 **0** 次，本卡迁移从未被执行；② 把本卡迁移文件从 `alembic/versions/` 移开后重跑同一条命令，HEAD 基线**同样 exit=1、同一句 `table profiles already exists`**（`logs/mixed-head-baseline.txt`），事后已归位并校验 md5 与 pristine 一致；③ CI 不会踩到，因为它给 smoke 与测试用两个不同文件（`ci.yml:143` 的 `build/ci_smoke.db` vs `ci.yml:166` 的 `build/ci_tests.db`）。归位建议：属部署/迁移链面，交 Lead 指派（本卡未改任何既有 revision） |
| schema 双路径一致性 | `logs/schema-smoke.txt`：迁移路径与 `Base.metadata.create_all`（`init_db()` 走的那条）建出的两张表**列集与索引集相同**；部分唯一约束实测撞出 `IntegrityError`；活行改 `revoked` 后新活行可插入（该 kind 总行数 2） |
| 定向（最终代码） | **53 passed / 31.47 s**（`logs/targeted-after-eol-normalise.txt`）。此前 `logs/targeted-final.txt` 53 passed / 31.57 s、`logs/targeted-after-reverse-proof.txt` 53 passed / 32.03 s。**首跑 51 passed / 2 failed / 33.62 s**（`logs/targeted-run1.txt`）不作记录数——两处失败都是本卡自己的用例期望写错，见 §20.4 |
| **反向验证：逐条禁用一条绑定规则（9 组）** | M1 撤 `source_run_not_completed` → **7 failed / 46 passed**（七态参数化全红）；M2 撤人类 actor 守卫 → **6 / 47**；M3 `active_memories` 改读全部状态 → **2 / 51**；M4 TTL 比较的 `moment`→`0.0` → **1 / 52**；M5 撤服务层 supersede 循环 → **2 / 51**；M6 `CONFIRMED` 事件写成 `SUPERSEDED` → **5 / 48**；M7 撤 revoke 幂等早返回 → **1 / 52**；M8/M9 让 `downgrade()` 两张表分支永假 → 各 **2 / 51**。变异前后 md5 逐一比对，9 组恢复后与 pristine **逐字节相同**，复跑仍全绿。补丁 `tmp/rp-M1..M9.patch`、日志 `logs/rp-M*.txt`、汇总 `logs/reverse-proof-summary.txt`。**工具替代登记**：本主机 `git apply -R` 被分类器拦，恢复一律用本卡自建的 `tmp/pristine/` 副本做纯文件复制（非 git 操作，只动本卡自己新建的两个文件） |
| 全量回归（**最终代码，记录数**） | `pytest tests/`（**2356** 项 = `--collect-only -q` 收 **2355** 项 + 集合期 1 条 `tests/a/test_mcp_readonly_protocol.py:11` 的 `importorskip("mcp")` skip，口径同 §17/§18/§19） → **2336 passed / 0 failed / 20 skipped / 1156.38 s（19:16）**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen201-2026-10-23/pytest-full`，探针 **`outbound attempts=0 unique_hosts=0`**、无用例因阻断转红；相对 104d 的 2283 恰好 **+53**，全为本卡新增项，既有用例零转红零消失。日志 `logs/full-suite.txt`（去 NUL 副本 `logs/full-suite-clean.txt`）、`logs/collect-quiet-probe.txt`（收集 11.79 s，探针 `attempts=0`）。**时长差要如实分开**：本轮 1156.38 s 比 104d 的 842.46 s 长 313.92 s，而本卡 53 项在 CI 同形旗标下只占 31.47 s，差额无法归因到本卡改动；同轮 warnings 由 22 → 25，新增三条全部落在 `tests/integration/test_manim_fallback.py`（1→3）与 `tests/integration/test_artifacts_api.py`（1→2）这两族计时敏感的既有用例上，本卡两个新文件零 warning——**这是线索，不是结论**，故此处只登记差异、不作解释 |
| CI 可移植子集 + CI 同形口径下的本卡用例 | `ci.yml:172-212` 的 **40** 个文件（**清单未扩**，本轮清单由 `awk` 从 `ci.yml` 机械重取，与 104d 的 `ci-portable-list.txt` 逐行相同） → **412 passed / 1 skipped / 80.92 s**，`--basetemp .../pytest-ci`，探针 `attempts=0 unique_hosts=0`；与 104d 的 412/1 **逐数相同**，正因为本卡两项不在该子集内（见 §20.4 未做清单第 4 条）。另按 `ci.yml:213` 同形旗标（`--no-cov --benchmark-disable -q`）单跑本卡两个文件：**53 passed / 31.58 s**，前置 `init_db()` 后 `create_all` 确实带出两张记忆表与全部索引；日志 `logs/ci-portable.txt`、`logs/ci-style-targeted.txt` |
| 静态门与口径 | CI 口径 `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed**；`git diff --check` 干净。裸 ruff（仓库未把风格规则纳入门禁，全仓基线 **13,647** 项）：`models.py` **18 → 18**（与 HEAD 基线逐条相同，本卡扩展零新增），4 个新文件合计 **24** 项 = `EM101` 18 + `EM102` 2 + `I001` 2 + `E501` 2；这四条规则在仓库里分别已有 **365 / 64 / 514 / 2907** 项同族命中，`EM101` 即"raise 里直接写字面串"——本卡要模仿的两个模块自己就在用它：`run_audit.py` 与 `run_usage.py` 合计 **6** 项，`backend/app/services` 整目录 **61** 项、`backend/app/agent_runtime` 整目录 **61** 项。`E501` 两处是 `tests/a/test_user_memory_service.py:64-65`（106/102 字符），折行即可消掉，但为让记录数与最终代码严格同一份，**全量跑完后未再动代码**，登记为下一卡的顺手项。`__tablename__` **37 → 39**；`--collect-only` 节点 id 去重后测试文件 **191 → 193**（+2 即本卡新文件），沿用 §18/§19 把集合期 mcp 文件也计入的口径则是 **192 → 194** |
| 行尾归一（一处本卡自造的噪音，如实登记） | 三个新文件初写成**纯 LF**，而本仓 `core.autocrlf=true`、既有文件是 `i/lf w/crlf`（对照 `alembic/versions/20261014_0011_login_attempts.py`）。`git add` 后索引一律是 LF、不产生错误 diff，但工作树形态与全仓不一致，故归一为 CRLF：转换前后按 LF 归一化 **md5 相同**（证明是纯行尾变换）、孤立 CR/LF **均为 0**；归一后五份文件的行尾计数 `models.py`=687、`user_memory.py`=270、迁移=56、服务测试=251、迁移测试=105，孤立 CR/LF 全为 0。归一后复跑定向 **53 passed / 31.47 s**。**次序要讲清楚**：全量 1156.38 s 那一轮跑的是归一前的 LF 形态，归一只动行尾、不动一字节内容，本卡不再宣称两者是同一份字节；旧拷贝存档在 `tmp/pre-crlf/` |

### 20.4 边界、自我更正与如实登记

- **两处失败改的都是测试期望，没有为绿放宽产品代码**：① `test_partial_unique_index_only_guards_active_rows` 初版断言"m-1 仍是 active 时再插一条 active 应成功"，与本卡自己的"一用户一 kind 只一条活"直接矛盾——正确做法是先把 m-1 置 `revoked` 再插，改后断言 active 计数 **1**、总行 **3**；② `test_a_superseded_expired_row_is_labelled_in_the_audit` 初版期望 `ttl_expired`，但紧接的第二次 `confirm` 时前驱尚未过期，产品行为给 `superseded_by:<id>` 是对的——测试改为先把 `expires_at` 回拨 120 s 再触发，两条分支都真正跑到。
- **未做清单**：① **API/UI 一律不碰**（§3-51 明留 203），本卡只有 schema + 服务层，**没有任何端点或前端消费这两张表**；② 跨会话摘要属 QWEN-202；③ `docs/API-CONTRACT.md:49`「Contract 4: DB 17 张表所有权」未改——该行被 `tests/b/test_contract_document.py:44` 字面断言，属 QWEN-103/401 的文档契约面，本卡两张表在 17 张之外，**口径漂移只登记不擅改**；④ 本卡两个新用例文件**未**纳入 `ci.yml:172-212` 的可移植 40 文件清单（清单未扩；`ci.yml:142-147` 的 alembic smoke 会自动跑到新迁移，无需改 CI）；⑤ `propose` 目前只被服务层与测试调用，**尚无生产者接线**——"谁在什么时机提候选"属 202/203 的产品面，本卡不猜；⑥ **PG 方言未实测**（DoD 只要求隔离 SQLite）：迁移给 `sqlite_where` 与 `postgresql_where` 各一份，服务层用 `.with_for_update()`——已核对编译差异，SQLite 侧编译不出 `FOR UPDATE`、PG 侧出，故本轮数字只在 SQLite 口径内成立，PG 层的 `CREATE UNIQUE INDEX … WHERE` 与行锁留给你的 pg 轮次（先例 QWEN-105）；⑦ §20.3 记录的"`init_db()` 后同库跑 `alembic upgrade head` 必红"属既有 revision 链现象，本卡未改任何既有迁移文件。
- 未向 `main` 提交或推送，只推 `qwen/wave2-memory`；**零模型调用、零外联**（每一轮都挂 fail-closed 探针并记 `attempts=0 unique_hosts=0`）；未 `cat`、未提交、未上传 `.env`；未起或重启服务；未加依赖。
- 旧登记继续在册：`reports/` 未被 gitignore、17 个前端孤儿测试、`multi.py` 行号漂移、`scripts/` 裸 ruff 全角标点基线 2382 项、可选 MCP stdio 步骤（`ci.yml:338-341`）本机未跑。

## 21. QWEN-201b 把记忆测试纳入 CI 快清单（2026-10-23，分支 `qwen/wave2-memory`，零模型调用）

Lead §4（`[2026-10-23 18:55]`，提交 `c28aac4` 时间 `18:50:40`）原文：「**QWEN-201b：把记忆测试纳入 CI 快清单（零模型）** — 继续 `qwen/wave2-memory`；把 `tests/a/test_user_memory_service.py`、`tests/a/test_user_memory_migration.py` 加入 `.github/workflows/ci.yml` 的 fast/portable 清单；更新 40→42 文件与通过数（预计 412→465/1，以实测为准），同步 README/TEST_MATRIX；不碰产品代码；跑一遍新清单确认全绿；完成后 `[DONE]`。」同一节记录 **QWEN-201 验收通过、已合并 `main`**，并裁定 §20.2 提请的三处读法（admin 不作为记忆确认者 / `revoke` 同样要求人类 actor / `source_type` 暂保留 32 字符自由串，闭集留待 202/203 需要时再开卡）。PG 方言 Lead 明示「交 CI enterprise 的 alembic 步骤与后续 PG 轮次复核，不在本卡扩范围」。

### 21.1 本卡改动（4 文件，唯一非文档改动是 `ci.yml` 的 2 行）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `.github/workflows/ci.yml` | portable 清单追加两份记忆测试，**40 → 42** | `:213-214`（清单本体 `:173-214`，hunk `@@ -212,0 +213,2 @@`，位于 `:212 test_deployment_policy.py` 之后、`:215` 旗标行之前） |
| `README.md` | 新增「CI 可移植子集（`quality` job 快清单）」一行，此前该表只有全量一行给用例数、无 CI 子集口径 | `:58` |
| `docs/TEST_MATRIX.md` | 新增 §18 | 标题行 `:448`，整节 `:448-459` |
| `docs/CLAIMS_LEDGER.md` | 本节 §21 | — |

产品代码、测试代码、迁移文件零改动。旧结论文本一律不改写：§20.3 那行「**清单未扩**」是 201 当时的事实，本节使其对下一轮失效，§20 原文保留。

### 21.2 一个自主取舍（如实登记，Lead 可要求改）

Lead 只说「加入 fast/portable 清单」，未指定插入位置。两个候选：紧跟 `tests/a/test_conversation_memory_v2.py`（`:207`，记忆主题相邻）或追加在清单尾部（`:212` 之后）。**选了尾部**，理由是本仓该清单的既有演化方式是追加（`test_run_leases.py`、`test_run_usage_admin.py`、`test_persistent_auth.py`、`test_auth_restart.py`、`test_deployment_policy.py` 即 104 系与运维卡依次追加），且 diff 为纯 `+2` 行、不动既有行序，验收时最容易复核。若 Lead 要按主题聚类，重排是一次纯位置改动，测试数不变。

### 21.3 实测（offline，零模型调用，探针 `attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 清单文件数 | **40 → 42**（与 201 清单逐行 diff = `40a41,42`） | `ci-portable-list.txt`（机械重取，42 路径存在性逐条检查 0 缺失） |
| CI 同形子集（**记录数**） | **465 passed / 1 skipped / 0 failed / 96.08 s** | `logs/ci-portable-final.txt`（`-rs`，点名唯一 skip `test_auth_restart.py:18`） |
| 同命令首跑 | 465 passed / 1 skipped / 112.98 s | `logs/ci-portable-run1.txt`（两跑计数一致，时长差属主机波动，不解释为结论） |
| 增量核对 | 412（201 同清单）+ **53** = 465，53 = 50 服务项 + 3 迁移项 | 与 §20.3 定向 53 passed 对得上；既有用例零转红 |
| 前置 `init_db()` | exit=0 | `logs/ci-init-db.txt` |
| alembic smoke（`ci.yml:141-147`） | upgrade head exit=0、downgrade base exit=0 | `logs/ci-alembic-smoke.txt` |
| CI ruff 门 | All checks passed（exit 0） | `logs/ci-ruff.txt` |
| workflow 本体 | YAML 解析 OK；`quality` 步 42 文件、`enterprise-contract` 仍 38 | `logs/ci-yaml-parse.txt` |
| 行尾 | `ci.yml` 341 → **343** 行、CRLF 与行数相等、孤立 LF/CR 各 0 | 字节统计（本卡编辑未破坏 `i/lf w/crlf` 一致性） |

外推限制：以上均为**本地按 CI 旗标同形复跑**（offline 证据等级），GitHub 上 `quality` job 的真实绿灯要等这次推送后的远程 run 回执，属 remote 证据、由 Lead 判读；本机无 `gh` CLI，不代跑远程。`test_auth_restart.py` 那条 skip 在 CI 上也依旧会 skip（它要求一次性 PostgreSQL），所以 465/1 在 CI 与本地口径一致。

### 21.4 未做与边界

- 未扩 `enterprise-contract` 38 文件 PG 清单（Lead 把 PG 方言复核交给该 job 的 alembic 步骤与后续 PG 轮次）；未动覆盖率门槛步。
- 未重跑全量 `pytest tests/`：本卡零新增用例、零产品改动，2336/0/20 / 2356 项的记录数不动；若 Lead 验收时想要一份同提交的全量数，我再跑，不在本卡擅自改记录数。
- 未动 `docs/API-CONTRACT.md:49`（Lead 本节已归 **QWEN-401/403**）、未动 baseline 迁移的无条件 `create_table`（Lead 本节已归 **QWEN-403**）。
- 未开始 QWEN-202：Lead 明示「201b 后开工」，分支 `qwen/wave2-summary` 已由 Lead 预建，待本节交付后按其顺序推进。
## 22. QWEN-202 跨会话摘要（2026-10-23，分支 `qwen/wave2-summary`，零模型调用）

Lead 2026-10-23 18:55 派工原文（`docs/QWEN_LEAD_DIALOGUE.md:1640-1644`）：「分支 `qwen/wave2-summary` 已由 Lead 预建；只基于 **active 且未过期** 的已确认记忆生成摘要；**摘要不得自动写回 `user_memories`**；无记忆时返回明确空态；只改服务/测试/文档，不碰 API/UI（203）；零模型、不读 `.env`；完成后 `[DONE]` 附测试数字与空态证据。」主计划同一张卡另有两句被本卡当验收口径执行（`docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md:487`）：范围「对完成 Run 生成有界摘要（**token 预算、幂等、失败回退**），替代固定 3 条窗口的**可配置版本**」，DoD「摘要忠实性测试（固定样例）；token 预算；不被 partial 污染」。

**编号说明（不是笔误，也别当漏写）**：§21 属 **QWEN-201b**（把两份记忆测试纳入 CI 快清单），已在 `qwen/wave2-memory` 交付并推送（`8ab00ab` + `a625adc`，`origin/qwen/wave2-memory = a625adc`），等你合并。本卡分支起点 `c28aac4` = `origin/main`，**不含 201b 的 `ci.yml`/README/矩阵/台账四处改动**，所以本节直接编 **§22**、矩阵编 **§19**，与 wave2-memory 上的 §21/§18 不撞号。两处都是文件末尾追加，合并时必然有文本冲突，但编号不需要返工。已用 `git merge-tree --write-tree a625adc HEAD` 只读干跑核实（输出 `output/qwen202-2026-10-23/logs/merge-tree-dry-run.txt`，exit 1）：**真冲突只有本台账与 `docs/TEST_MATRIX.md` 两处**，`README.md` 自动合并成功（201b 加 CI 行、本卡改本地全量行，不在同一行），导览文件 201b 未触碰。

### 22.1 改动（2 个新文件，产品代码之外零改动）

| 文件 | 改动 |
|---|---|
| `backend/app/services/session_summary.py`（新，180 行，CRLF，md5 `005986907fd116096b6f831c78fe7160`） | 两个入口 + 五个内部件：`estimate_tokens`（`:47`）、`_clip_to_tokens`（`:53`）、`_positive_int`（`:65`）、`_digest`（`:73`）、`_shape`（`:77`）、`_fit`（`:91`）、`build_summary`（`:100`）、`cross_session_summary`（`:154`）。**`build_summary` 的签名里没有 session**，和 201 的 `propose` 同一条结构约束：走到它的那条路不可能写库。`cross_session_summary` 收 `session_factory`，但库只做两件事——调 201 的 `active_memories`（`:165`，读）与 `select(AgentRunRecord.id, AgentRunRecord.status)`（`:170-174`，读），**没有 `add`/`commit`/`delete`/`flush`/`update`**。绑定常量集中在 `:28-32`：`DEFAULT_WINDOW=3`、`MAX_WINDOW=20`、`MAX_TOKENS_PER_MEMORY=80`、`DEFAULT_TOKEN_BUDGET=600`、`MAX_CHARS_PER_MEMORY=320`。复用而非另造：资格口径直接用 201 的 `MEMORY_ELIGIBLE_RUN_STATUS`（`:19`），异常直接用 `MemoryPersistenceError` / `MemoryPolicyViolation`（`:20-21`），**错误面零新增 code**，`memory_persistence_unavailable` 与 201 同族 |
| `tests/a/test_session_summary.py`（新，307 行 / **40 项**，24 个测试函数 + 3 组参数化展开成 19 项） | 逐项钉死 DoD：明确空态（含六个字段全等，`:48`）、固定样例金句 `- weak_point：分数除法还需要复习`（`:58`）、正文逐字忠实（每一行 `：` 右侧必须命中已存文本，`:71`）、**三次摘要后 `user_memories`/`memory_events` 行数仍是 `(1, 1)`**（`:85-93`）、幂等（`NOW` 与 `NOW+3600` 两次构建除 `generated_at` 外逐字段相同且 `summary_sha256` 相同，`:96`）、新记忆改变摘要哈希（`:106`）、未确认候选永不可摘要（`:115`）、revoked 掉出窗口（`:122`）、TTL 过期掉出窗口（`:132`）、**七态降级源 run 参数化**（`:145-147`：`partially_completed`/`failed`/`awaiting_approval`/`reviewing`/`interrupted`/`rejected`/`running`）、源 run 被删同样跳过（`source_run_not_completed:None`，`:160`）、手填记忆（无 `source_run_id`）仍可摘要（`:172`）、窗口 3/1/4 三档可配（`:179`）、预算截断（`:196`）、预算容不下任何一条 → 空态（`:207`）、超长裁剪带标记（`:216`）、坏行降级不拖垮整体（`:228`）、估算确定且非负（`:243`）、裁剪不越界（`:251`）、8 组非法预算参数（`:257-261`）+ 4 组缺失用户拒绝（`:266-267`）、**两次读各压一个稳定 code**（记忆库不可达 `:272`；源 run 表不可达 `:281`），以及一条**源码静态扫描**（`:300`）：本模块文本里不允许出现 `.add(`/`.commit(`/`.delete(`/`update(`/`llm`/`provider`/`requests`/`openai`/`http`/`os.environ`/`.env` |

本卡**没有**改 `backend/app/core/models.py`、没有新迁移、没有改 `user_memory.py`、没有动 API/UI/前端。表结构沿用 201 的 `user_memories` + `memory_events`。

### 22.2 这一层到底保证了什么

- **只读 active 且未过期**：过滤条件一条都不在本卡重写，直接调 201 的 `active_memories`（内含 `status='active'` 与 `expires_at IS NULL OR expires_at > now`）。两处口径不可能漂移，201 改这里，202 自动跟着改。
- **摘要绝不写回 `user_memories`**：三层同时成立——① `build_summary` 纯函数，签名里没有 session；② `cross_session_summary` 的 `with session_factory()` 块只跑 SELECT；③ 返回体恒带 `persisted: False`（`_shape`，`:88`）。实测两层：用例把两张表的行数在三次摘要前后钉死不变（`:93`）；`logs/empty-state-evidence.txt` 直接在真实 SQLite 上打印 `table counts after`，非空库读一次摘要仍是 `{'user_memories': 1, 'memory_events': 1}`。
- **明确空态**：空态不是 `None`、不是抛异常、也不是 `summary=""` 的摘要态，而是 `status="empty"` + 一个 `reason`，且 `sections/skipped/used_memory_ids/memory_count/estimated_tokens/summary_sha256/persisted` 全部照常给出，调用方不需要 try/except 分支。`reason` 分两类：`no_active_memory`（根本没有可读记忆）与 `no_memory_fit_budget`（有可读记忆，但预算容不下任何一条、或源 run 复核全部挡下）。
- **有界**：条数窗口 `window`（默 3、上限 20）+ 单项 token `MAX_TOKENS_PER_MEMORY=80` + 单项字符 `MAX_CHARS_PER_MEMORY=320` + 总量 `token_budget`（默 600、硬上限 100_000）。任何被裁、被跳的都显式出现在 `skipped`（`outside_window` `:140`、`token_budget` `:133`、`content_missing` `:121`、`source_run_not_completed:<status>` `:128-129`）与 `truncated` 里，不静默丢。
- **幂等**：`summary_sha256` 只对**输出正文行**做 sha256（`:87`），不含 `generated_at`、不含 `window`/`token_budget` 这类调用参数——同一份记忆在两个不同时刻构建，哈希一致。这是「consolidation 不重复劳动」的判据，不是装饰字段。
- **不被 partial 污染（在 201 之上补了读侧）**：写侧闸门 201 已有（`confirm` 当场核对源 run `status='completed'`）。但一条记忆确认后，它的源 run 状态仍可能变化（重跑、人工改判、行被删）。本卡在**读的时候再核一次**（`:127`），`run_statuses` 里不是 `completed` 就跳过并记 `source_run_not_completed:<status>`，因此「先确认、后降级」的记忆不会继续出现在摘要里。
- **失败回退**：单行坏数据（`content` 空白/非字符串）只让那一条变成 `content_missing` 跳过，整份摘要照常产出；两次读各自被同一个稳定 code 压住（`:175-178`），字符串就是 `memory_persistence_unavailable`，不带 DB 原文。
- **忠实性**：正文行格式固定 `- <kind>：<content>`，右侧逐字取自存储文本（超长才裁并以 `…` 结尾、并在 `truncated` 里标记），不生成、不改写、不合并、不翻译。
- **token 口径是离线启发式**：`tiktoken` 不是本仓依赖，本卡不引入外联也不加依赖，用「CJK 每字 1 token，其余 `⌈n/4⌉`」估算（`estimate_tokens`，`:47-50`）。它**只用来限长**，绝不作为计费/账单数字出现在任何接口或报告里；确定性、非负、单调（裁剪的二分谓词把省略号本身计入，所以返回值自身一定 `<= cap`）。

### 22.3 中途自查后的一处返工（如实登记，不是红点逼出来的）

`cross_session_summary` 初版把记忆那次读包进了 `try/except → MemoryPersistenceError("memory_persistence_unavailable")`，但**源 run 状态那次 SELECT 裸着**——本模块 docstring 承诺的是「两次读、只读、失败给稳定 code」，一条路径有兜底一条没有属于我自己写的不一致。补守卫（`:169-178`）+ 1 项用例（`:281`，故意让第二次 factory 抛异常），测试 **39 → 40 项**；因此**反向验证从 9 组扩到 10 组**（新增 R10 `run_read_guard`），定向、集合、全量与空态证据**全部在最终字节上重跑**；9 组阶段的日志整批移到 `logs/prev-39items/` 保留，守卫前的空态证据留在 `logs/prev-39items/empty-state-evidence-pre-guard.txt`，判定与最终一轮逐字相同。这一处只碰本卡自己的两个新文件，没动 201 的任何一行。

### 22.4 五处需你追认的取舍（本卡按字面实现，一处都没擅自扩）

1. **五个数字是我定的**：`3 / 20 / 80 / 600 / 320` 与 `token_budget` 硬上限 `100_000`。你的派工只写「有界」「token 预算」，主计划只写「替代固定 3 条窗口的可配置版本」，没有任何一处给数字。默认为 3 是照抄既有事实（`conversation_memory.py:21` 的 `.limit(3)`）。改口径只需动 `:28-32` 常量，逻辑不动。
2. **「可配置版本」我做成了服务层可配，没有回改 `backend/app/agent_runtime/conversation_memory.py:21` 的 `.limit(3)`**。那条是**请求路径**上的会话内记忆（把历史问答拼进 prompt），改它等于改运行时行为，而你本卡写「不碰 API/UI（203）」。**登记不改**，请你指派：并入 203，还是另开一张卡。
3. **无 `source_run_id` 的记忆**（教师/用户手填那条路）在本卡视为「没有可复核的 run」，直接放行参与摘要（`build_summary:124` 的 fallback）。若你认为手填记忆也要另立凭据，改动面就是那一行 fallback 改成跳过 + 一条用例。
4. **空态拆两个 `reason`** 是我的选择，你只要求「明确空态」。合成一个也能用，但会把「库是空的」和「库里有货但塞不下」这两种运维上完全不同的情形混成一类。
5. **`tests/a/test_session_summary.py` 未纳入 CI portable 清单**。你在 201 派工里点名要 201b 补两份记忆测试，202 派工条里没有这句，我不擅自扩清单。要补就是 `ci.yml` 尾部 +1 行、42 → 43 文件，同形子集按实测另跑一轮为准（本卡 40 项，量级 465 → 505/1 上下）。

### 22.5 实测（记录数）

| 量 | 值 | 证据 |
|---|---|---|
| 定向（最终交付字节） | **40 passed / 0 failed / 13.23 s**，探针 `attempts=0 unique_hosts=0` | `logs/targeted-after-reverse-proof.txt`（10 组反向验证逐条禁用并逐条按字节还原后的复跑） |
| 定向（补守卫后首跑） | 40 passed / 12.85 s | `logs/targeted-with-run-read-guard.txt`（同一批最终字节，反向验证之前） |
| 定向（39 项阶段，CRLF 归一后） | 39 passed / 20.00 s | `logs/targeted-run3-crlf.txt`；归一前同码 39 passed / 19.79 s（`logs/targeted-run2.txt`） |
| 首跑（**过程记录，不作记录数**） | 2 failed / 37 passed / 20.38 s（39 项） | `logs/targeted-run1.txt`。两处红点全在本卡自己的用例期望：① TTL 用例把 39 项版断言的 `NOW`（模块导入时的真实墙钟）当成了 `confirm()` 自己戳的时刻，差 6.8 s 撞 `abs=5`；② 手填记忆忘了 `run_id=None`，撞上 201 的 `source_run_not_found`。**改的是测试，没有放宽任何一条产品规则**；同轮另有一次 `_clip_to_tokens` 谓词的自查修正（把省略号计入长度），也不是被红点逼出来的 |
| 集合 | **2395** 项（`pytest tests/ --collect-only`，8.63 s）+ 集合期 1 条 `mcp` `importorskip` skip = **2396 项**，口径同 §20/§17 | `logs/collect-only.txt`，探针 `attempts=0` |
| 全量回归 | **2376 passed / 0 failed / 20 skipped / 993.55 s**，exit 0，195 个测试文件 | `logs/full-suite.txt`（含 NUL，去 NUL 副本 `logs/full-suite-clean.txt`，本轮所有数字取自该副本），`--basetemp output/qwen202-2026-10-23/pytest-full2`，探针 **`attempts=0 unique_hosts=0`**；相对 201 的 2336 恰好 **+40**，全为本卡新增项，既有用例零转红零消失 |
| 全量 warnings | 21 条（201 那轮 25、39 项那轮 26），warnings summary 里 `session_summary` 命中 **0** 次——是线索不是结论 | 同上 `logs/full-suite-clean.txt` |
| **反向验证：10 组各禁用一条绑定规则** | 同 40 项，每组 `failed + passed = 40` | R1 读时复核源 run 状态(不被 partial 污染)（禁用 `:127`）→ **8 failed / 32 passed**；R2 窗口截断（禁用 `:117`）→ **1 failed / 39 passed**；R3 token 预算（禁用 `:132`）→ **2 failed / 38 passed**；R4 超长裁剪（禁用 `:94`）→ **1 failed / 39 passed**；R5 空态原因区分（禁用 `:144`）→ **8 failed / 32 passed**；R6 persisted 恒为 False（禁用 `:88`）→ **3 failed / 37 passed**；R7 空内容降级（禁用 `:120`）→ **1 failed / 39 passed**；R8 摘要哈希只覆盖正文（禁用 `:87`）→ **1 failed / 39 passed**；R9 源码静态扫描禁止写回/模型（禁用 `:105`）→ **1 failed / 39 passed**；R10 源 run 那次读也压成稳定 code（禁用 `:175`）→ **1 failed / 39 passed**。 每组跑完立刻按字节还原，`md5` 与 pristine `005986907fd116096b6f831c78fe7160` 逐字节相同；每组的 pytest 调用自身也带探针，`attempts=0 unique_hosts=0` ×10。驱动 `reverse_proofs.py`、逐组日志 `logs/reverse-<组名>.txt`、汇总 `logs/reverse-proof-summary.txt`（含 `byte_restore_ok=True` ×10 与 10 条转红用例名） |
| 反向验证第一轮作废（如实登记） | 驱动初版把补丁写进共享 `body` 却没逐轮回滚，导致 R2–R4 的红点是**叠加**的（9/11/12 failed），且 `restore=False` | 发现后停进程、按 pristine 副本逐字节还原（`md5` 复核相同）、驱动改为每轮 `TARGET.write_bytes(original)` + `assert` 还原成功再跑下一组；四份被污染的日志改名 `logs/void-stacked-reverse-*.txt` 保留不删，不作证据 |
| **空态证据**（Lead 点名要的那件） | 真实 SQLite 上四种空态逐一打印完整返回体 + 每次之后的两表行数 | `logs/empty-state-evidence.txt`（脚本 `empty_state_evidence.py`，库 `tmp/empty-state-evidence.db`，**在最终字节上重跑**）：A 空库 → `empty/no_active_memory`，counts `{0, 0}`；B 只有未确认候选 → 同上，counts 仍 `{0, 0}`（201 的 `propose` 本就不落库）；C 有可读记忆但 `token_budget=1` → `empty/no_memory_fit_budget` 且 `skipped=[{…, 'token_budget'}]`，counts 仍 `{1, 1}`（**读一次摘要没多一行**）；D `revoke` 之后 → `empty/no_active_memory`，counts `{1, 2}`——**这两行增量全部来自 `memory.revoke()` 自己的审计事件，不是摘要写的** |
| 静态检查 | CI 口径 `ruff check --select=F821,F823,E9` 两个新文件 → **All checks passed**（exit 0） | `logs/ruff-final.txt`。裸 ruff（仓库未纳入门禁）两个新文件共 **15 项** = `RUF001` 7（中文全角冒号/括号，`session_summary.py:148` + 测试 6 处）+ `EM101` 4 + `EM102` 2 + `I001` 2；同族规则在本仓 `backend/app` + `tests/a` 范围内（**含本卡两个新文件**）已分别命中 `E501` 2221 / `RUF001` 3421 / `I001` 319 / `EM101` 252 / `EM102` 56（`logs/ruff-family-repo.txt`），本卡不是首例也不单独清洗 |
| 行尾与差异 | 两个新文件写成 CRLF：180 行 / 307 行，`crlf == 行数`、孤立 LF/CR 各 **0**；LF 原件留在 `tmp/pre-lf/`，CRLF pristine 在 `tmp/pristine-crlf/`（10 组反向验证的还原基准） | `git diff --check` 干净；`git status --porcelain` 全程只有这两个文件；`__tablename__` 仍 **39**、路由装饰器仍 **194**、`ci.yml` 本分支未动 |

外推限制：以上全部是**本机 offline 同形复跑**（Windows + Python 3.12.15）。GitHub 上的真实绿灯属 remote 证据、由你判读；PG 方言本卡零新表零迁移，不涉及。

### 22.6 未做与边界

- 未把 `test_session_summary.py` 加进 `.github/workflows/ci.yml` 的 fast/portable 清单（见 §22.4 第 5 条）；未动 `enterprise-contract` 38 文件清单；未动覆盖率门槛步。
- 未回改 `conversation_memory.py:21` 的 `.limit(3)`，也没让运行时去调 `cross_session_summary`（§22.4 第 2 条）。
- 未新增 API 端点、未改前端、未做 203 的记忆 UI；未接 `tiktoken` 或任何 tokenizer 依赖。
- 未动 201 的 `user_memory.py` / `models.py` / 迁移；未动 `docs/API-CONTRACT.md` 的表所有权行（Lead 已归 **QWEN-401/403**）；未动 baseline 迁移的无条件 `create_table`（已归 **QWEN-403**）。
- 未开始 QWEN-211（Phase A 顺序里的下一张，等你派）。

## 23. QWEN-202b 把跨会话摘要测试纳入 CI 快清单（2026-10-23，分支 `qwen/wave2-summary`，零模型调用、产品零改动）

Lead §4（`[2026-10-23 22:35]`，提交 `bbcc8e0`）原文：「**QWEN-202b（继续 `qwen/wave2-summary`，零模型）** — 把 `tests/a/test_session_summary.py` 加入 `.github/workflows/ci.yml` 快清单，42→43 文件；同形复跑预期 **505/1**（原 465 + 40），更新 README/TEST_MATRIX；产品零改动；完成后 `[DONE]`。」同一节记录 **QWEN-201b 与 QWEN-202 验收通过、已合并**（Lead 复跑 `test_session_summary.py` **40 passed / 12.61 s**，接受全量 2376/0/20），并把我提请在 §22.4 的五处取舍逐条裁定：默认值 `3/20/80/600/320` 与 `100_000` **接受**；`conversation_memory.py:21` 的 `.limit(3)` **本轮不改**（等 203/211 有产品需求再开卡，不夹带）；无 `source_run_id` 的手填记忆**允许**参与摘要；空态拆两个 `reason` **接受**；摘要测试进 CI **由本卡 202b 完成**。也就是说 §22.4 的五条已全部关闭，本卡就是其中第 5 条的落地。Lead 还手工解决了 201b 与 202 的文档追加冲突（台账 §21→§22、矩阵 §18→§19、对话两段都保留、编号不变，README 自动合并），所以本节的编号 **§23** 直接接在 §22 之后，无需再声明避让。

### 23.1 改动（1 个非文档文件，只加 1 行）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `.github/workflows/ci.yml` | `quality` job 的 portable 清单追加 `tests/a/test_session_summary.py`，**42 → 43 个文件** | 新行 `:215`（清单本体 `:173-215`，旗标行从 `:215` 顺移到 `:216`，hunk `@@ -212,6 +212,7 @@`，位于 `:214 test_user_memory_migration.py` 之后） |
| `README.md` | 改写 `:58` 的「CI 可移植子集」行：43 文件 / **505 passed / 1 skipped**，把 201b 的 465/1 降为同格历史 | `:58` |
| `docs/TEST_MATRIX.md` | 新增 §20 | — |
| `docs/CLAIMS_LEDGER.md` | 本节 §23 | — |

**产品代码、测试代码、迁移文件零改动**；`enterprise-contract` 的 38 文件 PG 清单未动；覆盖率门槛步未动。§21.2 那条「插入位置属自主取舍」在本卡复现：Lead 只说「加入快清单」，未指定位置，我仍选**清单尾部**（diff 为纯 `+1` 行、不动既有行序，最易复核）；若要按主题聚类与 `test_conversation_memory_v2.py` 相邻，是一次纯位置改动，计数不变。

### 23.2 实测（offline，零模型调用，探针 `attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 清单文件数 | **42 → 43**（与 201b 清单逐行 diff = `42a43`，43 条路径存在性逐条检查 0 缺失） | `ci-portable-list.txt`（由 `inspect_ci_list.py` 从 `ci.yml` **机械重取**，不是照抄上一轮清单） |
| CI 同形子集（**记录数**） | **505 passed / 1 skipped / 0 failed / 140.63 s**，4 条 warnings，exit 0 | `logs/ci-portable-final.txt`（`-rs`，点名唯一 skip 仍是 `test_auth_restart.py:18` 要求一次性 PostgreSQL） |
| 同命令首跑 | 505 passed / 1 skipped / 143.77 s | `logs/ci-portable-run1.txt`（两跑计数一致；时长差属主机波动，不解释为结论） |
| 增量核对 | 465（201b 同清单）+ **40** = 505，40 正是 §22 的摘要用例项数 | 与 Lead 派工条「预期 **505/1**（原 465 + 40）」**实测吻合**；既有 465 项零转红、零消失 |
| 前置 `init_db()` | exit=0 | `logs/ci-init-db.txt` |
| alembic smoke | `upgrade head` exit=0、`downgrade base` exit=0（共 24 条 Running 行 = 12 上 + 12 下） | `logs/ci-gates.txt` |
| CI ruff 门 | `--select=F821,F823,E9 backend/app scripts/ tests/` → All checks passed，exit 0 | 同上 `logs/ci-gates.txt` |
| workflow 本体 | `yaml.safe_load` OK；`quality` 步 **43** 文件、`enterprise-contract` 仍 **38** | `logs/ci-yaml-parse.txt` |
| 行尾 | `ci.yml` 343 → **344** 行、CRLF 与行数相等、孤立 LF/CR 各 0，md5 `2bf211180ec7435fd70cf711adf6c292` | 同上；`git diff --check` 干净，工作树除这 4 个文件外无改动 |

外推限制：以上全是**本机按 `ci.yml:216` 旗标同形复跑**（offline 证据等级）。GitHub 上 `quality` job 的真实回执属 remote 证据、由 Lead 判读；本机无 `gh` CLI，不代跑远程。`test_auth_restart.py` 那条 skip 在 CI 上同样会 skip，所以 505/1 两侧口径一致。PG 方言本卡零触碰（该文件未进 enterprise 清单）。

### 23.3 未做与边界

- 未重跑全量 `pytest tests/`：本卡零新增用例、零产品改动，§22 的 **2376/0/20 / 2396 项**记录数不动；若 Lead 验收时想要一份同提交的全量数，我再跑，不在本卡擅自改记录数。
- 未扩 `enterprise-contract` 38 文件 PG 清单，未动覆盖率门槛步，未动 MCP stdio 步。
- 未改 `docs/00-评委30秒导览.md`：Lead 本卡只点名 README 与 TEST_MATRIX，导览那行讲的是**全量**用例数（仍属 §22 的 2396 项），与本卡无关。
- 未动 `docs/API-CONTRACT.md:49`（归 **QWEN-401/403**）、未动 baseline 迁移的无条件 `create_table`（归 **QWEN-403**）。
- 未开始 **QWEN-211**：Lead 明示「202b 后开工」，分支 `qwen/wave2-planning` 已预建；本节交付后 hold，等你验收。

## 24. QWEN-211 有界重规划（2026-10-24，分支 `qwen/wave2-planning`，零模型调用）

Lead §4（`[2026-10-24 12:25]`，提交 `49910eb`）派发本卡，范围逐字：「1. 计划失效检测：工具失败 / 新证据与当前计划假设冲突时触发重规划；2. **最大重规划轮数与深度**硬上限（给基线常量即可，`[DONE]` 中标明；不要无限循环）；3. 每次重规划保留 checkpoint / 当前状态，可从 checkpoint 恢复；4. 超限时**停止并给出明确状态**，不是继续尝试；5. 测试覆盖：正常重规划、超轮数停止、超深度停止、checkpoint 恢复」，边界「只改 planner/agent runtime/测试/文档，不碰 API/UI；零模型、不读 `.env`；若最大轮数/深度等阈值需产品裁定，先给基线常量并在 `[DONE]` 中标明」；同一节还验收了 QWEN-202b 并把 211 之后的顺序定为 221 → 231 → 301 → 311/312 → 321/322/324 → 341/343 → 401/402/403 → 404。主计划 `docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md:489` 逐字：「QWEN-211 | Planning 有界重规划：工具失败/无证据时，最多 1 次换查询/换策略；记录原因与预算；不突破步数 | P1 | QWEN-103 | 3d | 失败路径测试；审计事件；文档」——本节按该 DoD 交付失败路径测试、审计事件与文档三件。

### 24.1 改动（1 个产品文件、1 个新测试文件、6 个文档文件，另加 §4 汇报）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `backend/app/agent_runtime/learning_package.py` | 唯一产品文件：失效检测、两条硬上限、失效账本、`plan.replanned` 审计事件与两条新路由 | `_REPLAN_REASONS` `:110-113`；`PackageState` 四个新字段 `:231-234`；`MAX_REPLAN_ROUNDS = 1` / `MAX_REPLAN_DEPTH = 2` `:258-259`；`_observed` 发事件 `:305-310`；`_invalidate_plan` `:390-411`；`_route_decide` / `_route_after_tool` `:413-421`；`_planner` 重规划分支 `:423-471`；`_decide` 停滞分支 `:486-489`；`_tool` 授权拒绝分支 `:507-510`、失败分支 `:511-520` |
| `tests/a/test_learning_package_replan.py` | **新增 15 项**，脚本化结构化输出桩驱动真实 API，零模型零网络 | `:32` 交付脚本、`:58-69` 失败检索注入、`:239-255` 检查点行、`:258-275` 断点恢复 |
| `docs/LEARNING_PACKAGE_GUIDE.md` | 上限表加 2 行（重规划轮数、单运行计划版本）+ 一段「有界重规划」说明 | 新行 `:34-35`；说明段 `:44` |
| `docs/ENTERPRISE_ARCHITECTURE_GUIDE.md` | §3.1 SSE 事件表加 `plan.replanned` 一行 | `:100`（原 `review.required` 行 `:99` 之后） |
| `README.md` | 全量行刷新为 2391/20，并把「211 未进 CI 快清单」写进 CI 行 | `:56`、`:58` |
| `docs/00-评委30秒导览.md` | 测试用例行刷新为 2411 项 | `:106` |
| `docs/TEST_MATRIX.md` / `docs/CLAIMS_LEDGER.md` | 新增矩阵 §21 / 本节 §24 | — |

`git diff --stat`：产品文件 **1 file changed, 121 insertions(+), 28 deletions(-)**（769 行、CRLF 769、孤立 LF/CR 各 0，md5 `f63b20beb98799dbb8c296321c0f3eba`）；新测试文件 300 行、纯 CRLF、md5 `49d2b437e07459ea3af918657892e56b`。**未碰** API 路由、SSE 契约字段、前端、迁移、DB、评测 harness、`.env`。

### 24.2 语义：什么算计划失效、上限怎么生效

- **两个触发（都是确定性可观测信号，不需要第二次模型判断）**。`tool_failed`：课程检索节点拿到 `failed`/`timeout` 状态的 `ToolResult`（`:511-520`，授权拒绝分支 `:507-510`）；`evidence_stalled`：模型重复使用已经检索过的提问、且此时证据集合仍为空（`:486-489`）。这就是 Lead 条 1 里「新证据与当前计划假设冲突」的可观测形式——计划假设「这个提问能拿到课程证据」被实际证据状态否证。语义级冲突判定需要额外模型或规则，属产品裁定，本卡不臆造（见 24.4）。
- **两条独立硬上限**：`MAX_REPLAN_ROUNDS = 1`（一个运行最多替换一次计划）与 `MAX_REPLAN_DEPTH = 2`（一个运行最多存在两版计划），任一耗尽即 `raise PackageFailure(stop_code)`（`:401-402`）。两个阈值各有用例单独把它压到 0/1 复验「上限本身是硬门」，而不是只验组合行为。
- **超限停止沿用根因错误码**，不新增用户可见 code：`learning_package_tool_failed` / `learning_package_repeated_search`。前端 `LearningPackageView.vue:104-106` 的 `run.failed` 分支按既有 code 映射文案，新增 code 会变成 API/UI 面改动，本卡按 Lead 边界不做。
- **不洗白任何既有上限**：`_invalidate_plan` 只清 `artifacts`/`practice_error`/`partial_completion` 与陈旧 `decision`，**不动** `budget`（`model_calls`/`tool_calls`/`input_chars`）、`searches`、`evidence`、`revisions`（`:393-395`、`:410-411`）。失败的那次检索仍然计费、其提问仍然记入 `searches`（`:513-520`），所以重规划后的计划不可能把同一个提问免费再跑一遍——用例把这条钉死：注入「第二次仍失败」时提问只执行 1 次、模型调用停在 4 次。
- **重规划不重放上下文工具**：`_planner` 在失效分支复用检查点里的 `planning_context`，不再读画像/错题/前置知识（`:427-430`），用例断言 `get_learning_profile`、`get_recent_mistakes` 各只调用 1 次。
- **不越权的三种情形明确排除**：检索预算耗尽（`searches >= MAX_TOOL_CALLS`）与「无证据直接 finish」是违约/授权停止，不是计划失效，仍走原来的 `learning_package_no_evidence`；`denied`/`invalid_args` 的工具是授权拒绝，重规划不可能让它变许可，直接失败（用例 `test_denied_tool_never_triggers_a_replan`）。
- **审计与可恢复性**：失效那一刻写 `plan_invalidation`（→ 合并进累积的 `plan_invalidations`）并由 `_observed` 发出 `plan.replanned` 事件（`:305-310`）。账本条目本身 8 个键——`trigger`/`round`/`plan_version`/`model_calls`/`tool_calls`/`input_chars`/`search_count`/`evidence_count`（`:404-409`）；审计事件与检查点行在此之上由 `_observed` 补一个 `node`，共 9 个键（`:310`），SSE 帧再自带 `run_id`/`event_sequence`，**不含**提示词、模型文本、检索内容、提问原文或计划正文；`record.result`、教师审核草稿 `approval` 与 GET 结果都不带账本（两个参数化用例覆盖 `require_approval` 两态）。崩溃/中断后 `POST /{run_id}/continue` 从检查点读回**已消耗的那一轮**：只重放失败节点并再次停止，不发放新的一轮，也不追加任何模型调用。

### 24.3 实测（offline，零模型调用，探针 `outbound attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 新用例 | **15 passed / 7.65 s**，exit 0 | `logs/new-file-final.txt` |
| 既有学习包/生命周期定向集（10 个文件，不含新文件） | **207 passed / 0 failed / 41.67 s** | `logs/targeted-package.txt` |
| 合并（学习包 + 生命周期 + 新用例） | **222 passed / 48.22 s**，0 红 | `logs/combined-package.txt` |
| **全量回归（记录数，最终字节）** | **2391 passed / 0 failed / 20 skipped / 901.89 s / 20 warnings**，`PYTEST_EXIT=0` 写进同一日志，196 个测试文件 | `logs/full-suite-repeat.txt`（去 NUL 副本 `full-suite-repeat-clean.txt`，本轮数字取自副本） |
| 同命令首跑（补最后一条「交付结果不含重规划账本」断言之前的字节） | 2391 passed / 0 failed / 20 skipped / 1079.94 s / 21 warnings，计数与记录数逐项一致 | `logs/full-suite-final.txt`（去 NUL 副本 `full-suite-final-clean.txt`）；定向跑与新文件跑全部在最终字节上 |
| **CI 同形子集（43 文件快清单，最终字节）** | **505 passed / 1 skipped / 0 failed / 135.49 s / 4 warnings**，`PYTEST_EXIT=0`，前置 `init_db()` exit=0；本卡产品改动没有让快清单里任何一项转红（清单内 7 个文件都跑学习包/生命周期） | `logs/ci-portable-final.txt`（去 NUL 副本 `ci-portable-final-clean.txt`）；清单由 `logs/ci-list-inspect.txt` 从 `ci.yml` **机械重取**，43 文件 0 缺失、`enterprise-contract` 仍 38 |
| 集合口径 | **2410** 个 node id +（`test_mcp_readonly.py` 收集期 `mcp` `importorskip` 产生的）1 条 = **2411 项**，收集 13.11 s | `logs/collect-only.txt`、`logs/collected-files.txt` |
| 相对上一记录 | 2391 = 你验收的 2376 + **15**，全为本卡新增；既有用例零转红、零消失 | 同上 |
| 重规划次数 | 交付路径 `planner` 节点 **2 次**、`plan.replanned` 事件 **1 条**、`trigger=tool_failed`、`round=1`；停滞路径同为 1 轮但 `decide` 4 次、模型调用 9 次 | `test_failed_retrieval_replans_once_and_still_delivers`、`test_stalled_search_replans_and_recovers_with_a_new_query`（`:80-93`、`:145-164`） |
| 超限停止日志 | 上限触发时产品自身记录 `Run <uuid> failed (PackageFailure)`（`run_lifecycle.py:269`），本轮 4 个关键用例共 **4** 条这样的停止日志，同时用例钉住 `run.failed` 载荷里的错误码与 0 条 `answer.delta` | `logs/replan-evidence-run.txt`（`--log-cli-level=INFO`，去 NUL 副本 `replan-evidence-clean.txt`） |
| 上限独立硬门 | `MAX_REPLAN_ROUNDS=0` 与 `MAX_REPLAN_DEPTH=1` 各自把运行钉在 `planner` 1 次、0 条 `plan.replanned`、错误码 `learning_package_tool_failed` | `test_replan_round_cap_is_an_independent_hard_limit`、`test_replan_depth_cap_is_an_independent_hard_limit`（`:167-186`） |
| checkpoint 恢复 | 断点续跑后仍是同一 `run.failed` 错误码，`node.started` 只有 `['tool']`，**模型调用数不变**、检索尝试从 2 增到 3、新事件 0 条 | `test_consumed_replan_round_survives_a_checkpoint_restart`（`:258-275`） |
| 审计事件持久化 | `agent_checkpoints` 里 `status='plan.replanned'` 恰 1 行、`node_name='planner'`、`state_data` 键集 = 上面那 9 个（含 `node`） | `test_replan_audit_event_is_persisted_as_a_checkpoint_row`（`:239-255`） |
| 反向验证（最终字节上复跑一轮） | **10 组全部被抓**，累计 **60** 个失败用例；每组改完后按字节还原产品文件（`PRODUCT_RESTORED_TO_PRE_ROUND_BYTES=1`、`ALL_10_MUTATIONS_CAUGHT`） | `logs/reverse-summary.txt`、`logs/reverse-R01..R10*.txt` |
| CI ruff 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → All checks passed；`compileall` OK | `logs/gates-ruff.txt` |
| 行尾与差异 | 全部 9 个改动/新增文件（1 产品 + 1 测试 + 7 文档，含 `docs/QWEN_LEAD_DIALOGUE.md` 的本节汇报）纯 CRLF、孤立 LF/CR 各 0；`git diff --check` 干净 | 写入脚本自带断言 + 本节 md5 |

### 24.4 需 Lead 裁定、边界与未做

- **基线常量待裁定**：`MAX_REPLAN_ROUNDS = 1`、`MAX_REPLAN_DEPTH = 2` 取自主计划「最多 1 次」，写成类常量、不读 `.env`、不接 API 参数。若产品要按课程/角色分档，是把常量搬到配置的动作，属 API/UI 面，本卡不做。
- **未做「语义级」失效检测**：只实现可观测信号（工具失败/超时、重复提问且证据为空）。若你要的是「新证据与计划假设冲突」的语义判定（例如检索结果与步骤 goal 不相关），那需要额外的模型判断或规则库，请另开卡并给预算。
- **未新增错误码**、未动 `PROMPT_VERSION`（仍 `learning-package-v2.8`）：重规划指令是**追加**的固定文案，与 `_review` 已有的「按状态追加指令」先例同类；bump 版本号会让 `LEARNING_PACKAGE_GUIDE.md:89`、`V2_TEN_MODULE_IMPLEMENTATION.md:58` 与 CLAIMS_LEDGER 的 T1 行集体漂移，那是独立文档工作。若你认为追加指令本身就该算提示词变更，说一声，我按 bump 流程重跑并逐处改文档。
- **未进 CI 快清单**：`.github/workflows/ci.yml` 仍是 43 文件 / 505 项，`tests/a/test_learning_package_replan.py` 未纳入（纳入属 2xx b 式独立卡，同 201b/202b 口径）；但本卡在最终字节上**同形复跑了这 43 个文件**确认既有的 505/1 记录不动（见 24.3）。PG 方言本轮未跑（该路径无 PG 专属行为，检查点恢复用例走仓库默认 SQLite + `InMemorySaver`）。
- **未动** `docs/API-CONTRACT.md:49`（归 401/403）、`conversation_memory.py:21`（归 203 之后）、`scripts/prepare_ablation_*.py`，未新增端点/UI。
- 证据等级：**offline**。全量数与定向数都来自本机同形复跑归档日志；GitHub `quality` job 与 PG 层不属本卡主张。

## 25. QWEN-211b 提示词版本 bump（v2.8 → v2.9）+ 重规划测试进 CI 快清单（2026-10-24，分支 `qwen/wave2-planning`，零模型调用、产品逻辑零改动）

Lead §4（`[2026-10-24 14:30]`，提交 `9d730fe`）派本卡，三条范围逐字：「**bump `PROMPT_VERSION` v2.8 → v2.9**：重规划追加了固定提示词，属提示词变更；同步 `docs/LEARNING_PACKAGE_GUIDE.md`、`docs/V2_TEN_MODULE_IMPLEMENTATION.md`、`docs/CLAIMS_LEDGER.md` 的 T1/v2.8 引用；不要改已有历史行。」「把 `tests/a/test_learning_package_replan.py` 加进 `ci.yml` 快清单 43→44，预期 **520/1**；更新 README/TEST_MATRIX；」「只改版本常量/文档/CI，不碰产品逻辑；完成后 `[DONE]`。」同一节验收 **QWEN-211**：Lead 本机复跑 `test_learning_package_replan.py` **15 passed / 8.91 s**，接受两类确定性失效信号、预算/检索不洗白、checkpoint + `plan.replanned` 审计、超限停止与全量 2391/0/20，并裁定 `MAX_REPLAN_ROUNDS=1` / `MAX_REPLAN_DEPTH=2` **接受**（先固定，按课程/角色分档属后续配置面）、语义级失效**另卡**。§24.4 的「基线常量待裁定」与「未做语义级失效」两条因此关闭，本卡落地剩下的「未 bump 版本」「未进快清单」两条。

### 25.1 改动（1 个产品常量行、1 个 CI 行、6 个文档文件，其中含本节与 §4 `[DONE]`）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `backend/app/agent_runtime/learning_package.py` | **只改 1 行常量**：`PROMPT_VERSION` `learning-package-v2.8` → `learning-package-v2.9`；路由、上限、事件载荷、节点函数逐字节不动 | `:23`；`git diff --stat` = 1 file changed, **1 insertion(+), 1 deletion(-)**；769 行、CRLF 769、孤立 LF/CR 各 0，md5 `39365d91586918122d7e72454f1ad498`（211 交付时 `f63b20beb98799dbb8c296321c0f3eba`） |
| `.github/workflows/ci.yml` | `quality` job 的 portable 清单尾部追加 `tests/a/test_learning_package_replan.py`，**43 → 44 个文件** | 新行 `:216`（清单本体 `:173-216`，同形旗标行从 `:216` 顺移到 **`:217`**，hunk `@@ -213,6 +213,7 @@`，位于 `:215 test_session_summary.py` 之后）；345 行、纯 CRLF，md5 `3658e9f11738a4633e72551947994080` |
| `docs/LEARNING_PACKAGE_GUIDE.md` | 版本行改写：写明 v2.9 的变更来源，并保留「v2.8 是 QWEN-102 云端采集与本批契约评测所用版本」 | `:93` |
| `docs/V2_TEN_MODULE_IMPLEMENTATION.md` | `PROMPT_VERSION` 常量与行号引用同步（`:20`→`:23`，行号后移因 211 在该文件新增了常量与状态字段） | `:58` |
| `docs/CLAIMS_LEDGER.md` | R4 / T1 / S7 三条**版本引用行**改成「现 v2.9；当时复核/采集为 v2.8」双时态，不动其余历史行 | `:31`、`:68`、`:98` |
| `README.md` | `:58` CI 行换成本卡 44 文件 / **520 passed / 1 skipped**，202b 的 505/1 与 201b 的 465/1 降为同格历史；`:56` 全量行补记「计数在 v2.9 最终字节上复跑逐项一致」 | `:56`、`:58` |
| `docs/TEST_MATRIX.md` | 新增 §22 | — |
| `docs/QWEN_LEAD_DIALOGUE.md` | 本节对应的 §4 `[DONE]` 汇报 | — |

**零改动**：`tests/a/test_learning_package_replan.py` 一字未动（300 行、纯 CRLF、md5 仍 `49d2b437e07459ea3af918657892e56b`），§24 的 15 项用例与 10 组反向验证不重跑不改动；`enterprise-contract` 的 38 文件 PG 清单、覆盖率门槛步、MCP stdio 步均未动。本卡交付面共 **8 个文件**：产品 1 行（`1 insertion(+), 1 deletion(-)`）、CI 1 行（`1 insertion(+)`）、文档 6 个（台账、矩阵、README、`LEARNING_PACKAGE_GUIDE.md`、`V2_TEN_MODULE_IMPLEMENTATION.md`、对话 `[DONE]`）。

### 25.2 语义：为什么这算提示词变更，以及哪些行必须留在 v2.8

- **算提示词变更**：211 在 `_planner` 的失效分支向 Planner 的 `instruction` **追加**固定文案（`:456-460`），而 `instruction` 由 `_ask` 拼进每个角色的 system prompt（`:322-324`，`PROMPT_VERSION` 插值就在 `:324`）并写进检查点与审计。也就是说 v2.8 这个标签下面现在同时存在「无重规划指令」和「带重规划指令」两种真实提示词文本，云端采集（QWEN-102）与本批契约评测用的都是前者。Lead 判「属提示词变更」即指此事，bump 是把标签跟回字节。
- **历史行不动**（Lead「不要改已有历史行」）：`docs/CLAIMS_LEDGER.md:140`（T1 在 103 修复时的复核记录）、`:901`（§24.4 交付当时记的「未动 `PROMPT_VERSION`」）、`docs/OPTIMIZATION_STATUS_2026-10-18.md:86`、`evals/results/independent-2026-10-19.md:3`、`evals/results/structured-output-20261018.md:16` 与 `docs/QWEN_LEAD_DIALOGUE.md:1859` 全部保留 v2.8——其中三处是**带日期的采集/修复证据本身**的口径，改成 v2.9 等于伪造当时的采集条件。
- **一处活文档未同步，登记不擅改**：`docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md:252` 仍写 `PROMPT_VERSION=learning-package-v2.8`。主计划不在本卡点名的三个文件里，且它是计划件而非现状件，我按越界登记处理；你说一句「同步 252」我就改。
- **没有测试钉住 `PROMPT_VERSION`**：全仓无对 `:23` 的断言（既有测试只断事件、状态与产物），所以 bump 在测试面上**静默**——`tests/a/test_learning_package.py` 的桩不看 system prompt 里的版本号。这属本卡「只改版本常量/文档/CI」之外的产品/测试面缺口，登记在此不擅自补用例。替代的机械校验是只读脚本 `output/qwen211b-2026-10-24/check_version_consistency.py`：解析产品常量及其行号，与两处文档锚点（各自唯一命中）逐字符比对，并列出台账 claim 表区（脚本取前 200 行，窗口外的 §24/§25 叙述行属明示历史）内仍点名 v2.x 的行，确认只剩带日期的 `:68`/`:140`；`VERSION_CONSISTENT=1`、`logs/version-consistency.txt`。

### 25.3 实测（offline，零模型调用，每条日志均记 `CMD:` 与 `PYTEST_EXIT=0`，探针 `outbound attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 版本一致性 | 产品常量 = `learning-package-v2.9`（`:23`），两处文档锚点（`:93`、`:58`）逐字符匹配且各自唯一命中；扫描窗口限于台账**前 200 行（claim 表区）**，其中仍点名 v2.x 的只有 `:68`/`:140` 两条带日期历史行（§24/§25 的叙述行在窗口外，属明示历史） | `logs/version-consistency.txt`（`VERSION_CONSISTENT=1`） |
| CI 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → All checks passed（exit 0）；`compileall backend/app tests/` exit 0 | `logs/gates.txt` |
| 前置 `init_db()` | exit 0 | `logs/ci-init-db.txt` |
| 清单文件数 | **44**（`yaml.safe_load` 从 `ci.yml` **机械重取**，非照抄上一轮）；44 条路径存在性 0 缺失；末位即本卡新纳入的文件；无重复 | `logs/portable-list.txt`、`logs/ci-list-inspect.txt` |
| **CI 同形子集（44 文件，最终字节）** | **520 passed / 1 skipped / 0 failed / 4 warnings / 145.34 s**，旗标按 `ci.yml:217` 同形（`--no-cov --benchmark-disable -q -rs`） | `logs/ci-portable.txt`（去 NUL 副本 `ci-portable-clean.txt`）；唯一 skip 仍是 `test_auth_restart.py:18` 要求一次性 PostgreSQL |
| 增量核对 | 505（202b 同清单）+ **15** = **520**，15 正是 §24 的重规划用例项数 —— 与 Lead 派工条「预期 **520/1**」**实测吻合**；既有 505 项零转红、零消失 | 同上 |
| 新文件单跑 | 15 passed / 7.62 s | `logs/new-file.txt` |
| 既有回归面 | 10 个学习包/生命周期文件 **207 passed / 39.83 s**；合并 **222 passed / 45.86 s**（= 207 + 15） | `logs/targeted-package.txt`、`logs/combined-package.txt` |
| **全量（v2.9 最终字节）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen211b-2026-10-24/pytest-full-suite`）**2391 passed / 0 failed / 20 skipped / 1308.53 s / 21 warnings**，196 个测试文件 / 2411 项 | `logs/full-suite.txt`（去 NUL 副本 `full-suite-clean.txt`）；与 §24 的 2391/0/20 **逐项一致**，本卡零新增用例故记录数不动；warnings 取自 summary 行，§24 记录数轮为 20 条，该数随轮次波动、不解释为结论；1308.53 s 与 §24 的 901.89 s 之差属同机负载（同命令、同口径），同样不作结论 |
| 集合口径 | **2410** 个 node id +（`test_mcp_readonly_protocol.py` 收集期 `mcp` `importorskip`）1 条 = **2411 项**，收集 15.97 s | `logs/collect-only.txt` |
| 字节与行尾 | 本卡 8 个改动文件全部纯 CRLF、孤立 LF/CR 各 0：`ci.yml` 344→**345**、产品 769 行不变、`LEARNING_PACKAGE_GUIDE.md` 111、`V2_TEN_MODULE_IMPLEMENTATION.md` 81、`README.md` 225（只换两行、不增行）、台账 904→**955**、矩阵 525→**544**；`git diff --check` 干净 | `logs/bytes-inventory.txt` + 写入脚本自带断言 |

### 25.4 边界与未做

- **产品逻辑零改动**：只动 `:23` 一行常量。路由（`:413-421`）、两条上限（`:258-259`）、`_invalidate_plan`（`:390-411`）、`plan.replanned` 载荷（`:305-310`）逐字节未变，故 §24 的语义主张全部继承，不需重跑反向验证（本卡也没重跑）。
- **未补钉版本的用例**（见 25.2 末条），**未同步主计划** `:252`，**未改** `docs/00-评委30秒导览.md:106`：那一行讲的是**全量**用例数（仍 2411 项 / 2391 passed），本卡零新增用例故数值不动，Lead 本卡只点名 README 与 TEST_MATRIX。
- **未跑** GitHub `quality` job 真实回执、未跑 PG `enterprise-contract` 38 文件清单（本卡无 PG 面改动；那条 skip 在 CI 上同样 skip，两侧口径一致）。
- **未开始 QWEN-221**：Lead 明示「211b 后」，分支 `qwen/wave2-tools` 已预建；本节交付后 hold，等你验收。
- **顺带更正 §24.3 / 矩阵 §21 的两处 warnings 数**：那两行写的是 `11 warnings`，来自脚本在日志正文里**首次**匹配到「N warnings」，不是 pytest 的 summary 行；按 summary 行重取为 **20**（记录数轮 `full-suite-repeat.txt`）与 **21**（首跑轮 `full-suite-final.txt`），本卡把这两行改成正确数值（矩阵 §21 同步），passed/skipped/时长/项数等其余结论一字未动。本卡的解析器只从 summary 行取数（`write_docs_211b.py::summary`），故不再受正文里同类字符串影响。
- 证据等级：**offline**。全部为同机同形复跑归档日志；GitHub 回执属 remote、PG 层未触及，均不属本卡主张。

## 26. QWEN-211c 版本防漂移断言（钉住 `PROMPT_VERSION` 字面值）（2026-10-24，分支 `qwen/wave2-planning`，零模型调用、产品逻辑与 CI 零改动）

Lead §4（`[2026-10-24 15:35]`，提交 `4ba955a`）先验收 **QWEN-211b**（「`PROMPT_VERSION=v2.9`，文档保留双时态…CI 43→44 文件，同形 **520 passed / 1 skipped**；全量 **2391/0/20**；接受。」「主计划 `docs/QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md:252` 的 v2.8 引用**由我同步为 v2.9**」「你登记的 warnings 数更正（11→20/21）接受」），再派本卡，四条逐字：「在 `tests/a/test_learning_package_replan.py` 内加一条断言 `PROMPT_VERSION == "learning-package-v2.9"`（**只加用例项，不新增文件**）；」「预期全量 **2392/0/20**、CI 快清单 **521/1**；更新 README/矩阵计数；」「**只改测试/计数文档，不碰产品逻辑**；完成后 `[DONE]`。」「之后 **QWEN-221** 在 `qwen/wave2-tools`（已预建）开工」。§25.2 登记的「全仓没有任何测试断言 `PROMPT_VERSION` 的字面值，bump 在测试面上静默」这一缺口由本卡关闭。

### 26.1 改动（1 个测试文件的纯尾部追加 + 4 个文档文件，另加 §4 汇报）

| 文件 | 改动 | 锚点与字节 |
|---|---|---|
| `tests/a/test_learning_package_replan.py` | 追加**一条**无 fixture 的用例 `test_prompt_version_is_tagged_for_the_added_replan_instruction()`，断言 `PROMPT_VERSION == "learning-package-v2.9"`；既有 15 项一字未动 | `git diff --numstat` = **8 insertions(+), 0 deletions(-)**，hunk `@@ -300,0 +301,8 @@`（纯尾部追加，前 300 行在 LF 归一化下与 `git show HEAD:` 逐字节相同）；308 行、纯 CRLF、孤立 LF/CR 各 0，md5 `49d2b437e07459ea3af918657892e56b` → **`a530f5a6342dcfa7eb6c145539cccfaa`**；新断言在 `:308` |
| `docs/CLAIMS_LEDGER.md` | 新增本节 §26（追加，不回改 §24/§25） | — |
| `docs/TEST_MATRIX.md` | 新增 §23 | — |
| `README.md` | `:56` 全量行换成本卡 2392/0/20 记录、211 与 211b 的 2391/0/20 降为同格历史；`:58` CI 行换成本卡 521/1、211b 的 520/1 降为同格历史 | `:56`、`:58` |
| `docs/00-评委30秒导览.md` | `:106`「测试用例」行随全量计数改为 **2412 项**（2392 passed / 0 failed / 20 skipped），QWEN-211 那轮降为同格历史 | `:106` |
| `docs/QWEN_LEAD_DIALOGUE.md` | 本节对应的 §4 `[DONE]` 汇报 | — |

**零改动**：`backend/app/agent_runtime/learning_package.py`（769 行、md5 仍 `39365d91586918122d7e72454f1ad498`，与 211b 交付时逐字节相同）与 `.github/workflows/ci.yml`（345 行、md5 仍 `3658e9f11738a4633e72551947994080`，快清单仍 44 个文件、`enterprise-contract` 仍 38）——`inspect_ci_list_211c.py` 从本轮 `ci.yml` 自身字节经 `yaml.safe_load` 机械重取并断言 md5，输出 `CI_UNTOUCHED=1`。

### 26.2 语义：这条断言钉住的是什么

- **钉的是产品字面值，不是文档字符串**：用例 `from backend.app.agent_runtime.learning_package import PROMPT_VERSION` 后与字面量比较，因此 `backend/app/agent_runtime/learning_package.py:23` 一旦漂移（例如后续卡片补提示词却忘记 bump，或反向把已 bump 的版本改回去），CI 快清单里这条用例当场转红。反向验证（§26.3）就是按此执行：把常量临时改回 v2.8，**整文件 15 passed / 1 failed**、单跑新用例 **1 failed**，恢复字节后复跑 **16 passed**。
- **三方一致性由只读脚本机械核对**（`check_version_consistency_211c.py` → `logs/version-consistency.txt`，`PRODUCT_TEST_DOC_AGREEMENT=1`）：产品 `:23` = 测试 `:308` = `docs/LEARNING_PACKAGE_GUIDE.md:93` = `docs/V2_TEN_MODULE_IMPLEMENTATION.md:58` 都是 `learning-package-v2.9`；主计划 `:252` 现也写 v2.9（Lead 在 §4 `[2026-10-24 15:35]` 自行同步，本卡未动计划件）；台账 claim 表区（前 200 行）仍点名 v2.x 的只剩 `:68`/`:140` 两条带日期历史行。
- **§25.2 的缺口登记就此关闭**：211b 交付时「没有测试钉住版本、只能靠只读脚本」的状态已被本卡替换；§25 正文按其交付当时的事实保留，不回改。

### 26.3 实测（offline，零模型调用，每条日志均记 `CMD:` 与 `PYTEST_EXIT`，探针 `outbound attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 新文件（16 项 = 15 + 1） | **16 passed / 0 failed / 8.45 s**，`PYTEST_EXIT=0` | `logs/new-file.txt` |
| 既有回归面 | 10 个学习包/生命周期文件 **207 passed / 43.31 s**；合并 **223 passed / 52.34 s**（= 207 + 16） | `logs/targeted-package.txt`、`logs/combined-package.txt` |
| **CI 同形子集（44 文件）** | **521 passed / 1 skipped / 0 failed / 4 warnings / 148.33 s**，旗标按 `ci.yml:217` 同形（`--no-cov --benchmark-disable -q -rs`）+ 前置 `init_db()`；相对 211b 的 520 恰好 **+1** = 本卡新增用例项数，与 Lead 派工预计 **521/1** **实测吻合**；唯一 skip 仍是 `test_auth_restart.py:18` | `logs/ci-portable.txt`（去 NUL 副本 `ci-portable-clean.txt`）、`logs/portable-list.txt`、`logs/ci-init-db.txt` |
| **全量（记录数）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen211c-2026-10-24/pytest-full-suite`）**2392 passed / 0 failed / 20 skipped / 853.50 s / 23 warnings**，196 个测试文件 / **2412 项** | `logs/full-suite.txt`（去 NUL 副本 `full-suite-clean.txt`）；与 Lead 预计 **2392/0/20** 一致 = §25 的 2391 + 本卡 1 项 |
| 集合口径 | **2411** 个 node id +（`test_mcp_readonly_protocol.py` 收集期 `mcp` `importorskip`）1 条 = **2412 项**，收集 14.99 s | `logs/collect-only.txt` |
| 反向验证 | 临时把 `:23` 改为 v2.8（**未提交**，`finally` 内按字节恢复）：整文件 **1 failed / 15 passed / 8.60 s**，失败的正是新用例；单跑新用例 **1 failed / 2.31 s**；恢复后 md5 = `39365d91586918122d7e72454f1ad498`、`git diff --stat -- backend/` 为空，再复跑 **16 passed / 7.29 s** | `logs/reverse-with-patched-constant.txt`、`logs/reverse-new-case-only.txt`、`logs/post-restore.txt`、`tmp/product-v2.9-backup.bin` |
| CI 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → All checks passed（exit 0）；`compileall backend/app tests/` exit 0；前置 `init_db()` exit 0 | `logs/gates.txt`、`logs/ci-init-db.txt` |
| 字节与行尾 | `ci.yml` 345 行 md5 `3658e9f11738a4633e72551947994080`（**本卡未动**）、产品 769 行 md5 `39365d91586918122d7e72454f1ad498`（**本卡未动**）、测试 308 行纯 CRLF md5 `a530f5a6342dcfa7eb6c145539cccfaa`；`git diff --check` 干净 | `logs/ci-list-inspect.txt`、`logs/append-verify.txt`、`logs/baseline-bytes.txt` |

### 26.4 边界与未做

- **只加用例项、不新增文件**（Lead 原话）：文件内 14 个 `def test_` 增至 15 个，条目 15 → 16（`@pytest.mark.parametrize` 那条仍贡献 2 项）；未新建测试文件、未动既有任何一行。
- **未碰产品逻辑与 CI**：见 §26.1 末段的 md5 断言；反向验证里对产品常量的临时改动**只存在于工作树**，运行结束即按字节恢复，未进任何提交。
- **未跑** GitHub `quality` job 真实回执（本机无 `gh`，属 remote 证据）、未跑 PG `enterprise-contract` 38 文件清单（本卡零 PG 面改动，同 §23/§25 口径）。
- **`docs/QWEN_LEAD_DIALOGUE.md:1890`（§25 的 §4 汇报）与 §25 正文一字未改**；本卡的汇报作为新的 §4 一节追加。
- **两轮作废记录保留、不掩盖**：`logs/void-append-crash.txt` 是追加脚本自己的行数预期写错（漏算了顶层 `def` 前需要两行空行，307 → 实际 308），`AssertionError` 在写完文件之后才触发；随后用 `verify_append_211c.py` 独立复核「前 300 行与 HEAD 逐字节相同 + 只追加 8 行 + 只多 1 个 `def`」，结论不受影响。`logs/void-reverse-*.txt` 是反向验证首跑：`PYTHONPATH` 把轮次目录错拼成 `ROOT/目录名`，pytest 在插件导入阶段就报 `ImportError: qwen_net_probe`，那两次 `exit=1` **属脚手架错误、不是红点**，所以整轮作废重跑；修正后的驱动加了三条断言（必须有 pytest summary 行、日志不得含 ImportError、红点必须点名新用例），结果见 `logs/reverse-summary.txt`。
- 计数与预期全部按 pytest summary 行取数（`parse_211c.py::summary`），不看日志正文里第一次出现的「N warnings」；本轮全量 23 条 warnings（§24 记录数轮 20、§25 轮 21）随轮次波动，不作结论。
- 证据等级：**offline**。全部为同机同形复跑归档日志；GitHub 回执与 PG 层不属本卡主张。

## 27. QWEN-221 单一工具目录（ToolRegistry 元数据）+ 运行时 deny-by-default + 统一审计（2026-10-24，分支 `qwen/wave2-tools`，零模型调用）

Lead §4（`[2026-10-24 16:15]`，提交 `1ffc282`）先验收 **QWEN-211c**（「新增 `PROMPT_VERSION == "learning-package-v2.9"` 断言（15→16 项）；CI 快清单 **521/1**、全量 **2392/0/20**；产品与 `ci.yml` 零改动；接受」），再派本卡：「**QWEN-221：现在开工（允许，不适用交付后 hold）**」「`qwen/wave2-tools` 已由我 fast-forward 到 `main@13ea358`，直接在该分支工作，无需建分支」。范围五条逐字：

1. 「**单一 ToolRegistry 元数据**：工具名、允许角色、参数 schema、只读/副作用、超时、权限键」；
2. 「运行时 **deny-by-default**：未知工具、未授权角色、非法参数一律拒绝并写审计事件」；
3. 「替换散落的工具白名单/注册，保留现有调用行为与稳定错误面」；
4. 「测试覆盖越权拒绝、未知工具、schema 错误、审计；不碰 API/UI/前端；零模型、不读 `.env`」；
5. 「`[DONE]` 附权限矩阵基线、越权测试与审计证据」。

另两句约束照抄：「若工具角色划分需要产品裁定，先给基线矩阵并在 `[DONE]` 标明，不擅自扩到 API/UI」「**之后**：221 → 231 → 301 → 311/312 → 321/322/324 → 341/343 → 401/402/403 → 404；P2 后置」。§3-71 的原卡要求（「合并 V1 registry/V2 broker 接口；角色×课程×Run×参数校验；超时/配额/截断；统一审计」）与主计划验收口径（「迁移现有工具；矩阵测试；V2 回归全绿；新增工具只接一处」）一并作为本卡验收面。

### 27.1 改动（2 个新模块 + 2 个既有注册面 + 1 个新测试文件 + 5 个文档文件）

| 文件 | 改动 | 锚点与字节 |
|---|---|---|
| `backend/app/services/tool_catalog.py`（**新增**） | 9 个工具各一条 `ToolSpec`：工具名、来源（`v1`/`v2`）、描述、权限键、允许角色、只读/副作用、版本、超时与超时类、参数模型（V2 用 pydantic）或 JSON schema（V1 用 `parameters`/`required`）、结果截断上限、是否 MCP 暴露；另有 `ROLE_PERMISSIONS`（角色→权限键）、`decide_access()`、`matrix_violations()`、`source_specs()`、`tools_for_role()`、`v2_timeouts()`（默认超时从 spec 派生，不写字面量） | 215 行、纯 CRLF、孤立 LF/CR 各 0、md5 `3c13c4490298567bf34b6986e6c86656`；模块导入期 `assert len(TOOL_CATALOG) == len(_SPECS)` 拒绝重名 |
| `backend/app/services/tool_audit.py`（**新增**） | 统一审计：14 个固定键（`tool/source/version/role/run_id/session_id/status/decision/reason/permission_key/side_effect/timeout_seconds/latency_ms/request_hash`）、`ToolAuditLog` 环形 500 条、`counts()` 汇总 `total/granted/refused/by_status/by_decision/by_tool`、`recent(tool=, decision=)`；键集漂移直接 `raise ValueError`，API 不收任何参数值（传 `query=` 是 `TypeError`） | 123 行、纯 CRLF、md5 `7cb62306d6677cbb980000240b5bab39` |
| `backend/app/services/v2_learning_tools.py` | **删除** `ROLE_TOOLS`、`SCHEMAS`、`_Args`/`SearchArgs`/`EmptyArgs`/`PrerequisiteArgs`（迁到目录）；`call()` 的权限、参数校验、超时、截断全部改读 `ToolSpec`；每次调用仍重查持久课程授权；`TOOL_VERSION`、`ToolContext`、`ToolResult`、`V2LearningTools` 四个公开符号与六态错误面（`success/no_data/denied/invalid_args/timeout/failed`）、`audit()` 六键一字未动 | 171 行（HEAD `1ffc282` 为 180 行、md5 `ba7c1a49bda932a440eeeb6d6245be37`）、md5 `e17a28b1da38837f4b983e51b5635233`、`git diff --numstat` **46 / −55** |
| `backend/app/services/agent_tools/registry.py` | 5 个 `ToolSchema` 字面量改为 `for spec in source_specs("v1")` 循环构造（handler 名字表仍在本文件）；`_traced_call` 入口加同一 `decide_access(INTERNAL_ROLE, tool)` 闸门：未登记名字**不再执行 handler**，返回既有结构化失败 `{success: False, error: "tool_access_denied: <reason>", tool}` 并写一条审计事件；放行/异常各写一条（`reason` 只存异常类名）；`ToolSchema`/`ToolRegistration`/`list_a_tools()`/`to_openai_tools()`/`ToolCallTrace` 全部保留 | 503 行（HEAD 为 527 行、md5 `c83f3c571d4d3ff5474d0c2b69fc2296`）、md5 `8b6844c70c32fd516d9ff4ef62b9693a`、`git diff --numstat` **47 / −71**；`to_openai_tools()` 与 `git show HEAD:` 版本逐字节相同（`compare_openai_export.py` → `OPENAI_EXPORT_IDENTICAL=1`、`ORDER_SAME=True`、`OWNER_SAME=True`） |
| `tests/a/test_tool_registry_permissions.py`（**新增**） | 18 条用例，执行面一律换成 spy（拒绝类用例断言 spy `calls == []`）：目录 9 条唯一声明、基线矩阵逐字钉、**4 角色 × 9 工具全量越权扫**、未知工具/未知角色、错误面稳定、schema 四类非法参数（注入键 / 空 / 全空格 / 超长 / 缺必填 / 类型错）、空范围、超时+截断+执行失败+授权撤销、一调用一事件（6 种结局逐条比对顺序与状态）、事件元数据只从 spec 派生、V1 闸门与错误面、OpenAI 投影、MCP 的 `ast` 名字+入参名平价、散落白名单确已删除、V1/V2 两种 schema 风格分工 | 395 行、纯 CRLF、md5 `af49171bb284a43725e312b8571d8ef2`；零 DB、零模型、零网络（`mcp` 未安装也不影响：MCP 面用 `ast` 读源码） |
| `docs/CLAIMS_LEDGER.md` / `docs/TEST_MATRIX.md` | 新增本节 §27 / 新增 §24（**追加**，不回改 §24/§25/§26 与各矩阵节） | — |
| `README.md` | `:56` 全量行换成本卡记录、211c 那轮降为同格历史；`:58` CI 行换成本卡 44 文件同形复跑与 45 文件候选清单 | `:56`、`:58` |
| `docs/00-评委30秒导览.md` | `:106`「测试用例」行随全量计数刷新 | `:106` |
| `docs/V2_TEN_MODULE_IMPLEMENTATION.md` | `:30`/`:31`：工具名/角色/权限键/超时/参数模型的落点由 `v2_learning_tools.py` 改指 `tool_catalog.py`，并补记统一审计事件（拒绝也写） | `:30`、`:31` |
| `docs/QWEN_LEAD_DIALOGUE.md` | 本节对应的 §4 `[DONE]` 汇报 | — |

**本卡零改动（逐字节断言）**：`backend/app/mcp_readonly.py`（70 行、md5 `6eea05e5fef4622ae314f9e1e1654e03`，与 HEAD 相同——本机未装 `mcp`，改了也无法本地验证，改为用新用例做 `ast` 平价）、`.github/workflows/ci.yml`（345 行、md5 `3658e9f11738a4633e72551947994080`；`quality` 快清单仍 **44** 文件、`enterprise-contract` 仍 **38**，`inspect_ci_list_221.py` 经 `yaml.safe_load` 机械重取并断言 md5 → `CI_UNTOUCHED=1`）、`backend/app/api/v2/learning_runs.py`（431 行、md5 `8d2730e73b6dd54ee284a64cc14ac417`，`LearningRuntime.call_tool` 仍是那层薄适配）、`backend/app/agent_runtime/learning_package.py`（769 行、md5 `39365d91586918122d7e72454f1ad498`）。

「与 HEAD 相同」在这一轮用三条判据同时成立来定（`logs/final-bytes.txt`）：工作树 md5 = 前一轮（§25/§26）记录值、EOL 归一化后与 `git show HEAD:` 的 blob 逐字节相同、`git diff HEAD -- <file>` 为空。原因是本仓存 LF、本机检出 CRLF，blob md5 与工作树 md5 天然不同（`ci.yml` blob `f43925…` vs 工作树 `3658e9…`），单看 md5 字符串会把这条主机事实误读成改动。

### 27.2 基线权限矩阵与语义

矩阵由 `matrix_dump_221.py` **从目录本身导出**（`logs/permission-matrix.txt`，`MATRIX_DUMP_OK=1`），不是手写：

| 工具 | 来源 | 允许角色 | 权限键 | 副作用 | 超时(秒) | 必填参数 | 全部参数 | 截断 | MCP |
|---|---|---|---|---|---|---|---|---|---|
| `search_course_evidence` | v2 | tutor | `course:evidence:search` | 否 | 30 (search) | `query` | `query` | 5 | 是 |
| `get_learning_profile` | v2 | planner | `learning:profile:read` | 否 | 10 (standard) | (无) | (无) | - | 是 |
| `get_recent_mistakes` | v2 | planner | `learning:mistakes:read` | 否 | 10 (standard) | (无) | (无) | - | 是 |
| `get_prerequisites` | v2 | planner | `learning:prerequisites:read` | 否 | 10 (standard) | `knowledge_point_id` | `knowledge_point_id` | - | 是 |
| `lookup_knowledge_point` | v1 | system | `knowledge:lookup` | 否 | -（handler 自持） | `kp_name` | `kp_name` | - | 否 |
| `query_knowledge_graph` | v1 | system | `knowledge:graph:query` | 否 | -（handler 自持） | `kp_name` | `hop`/`kp_name` | - | 否 |
| `execute_code` | v1 | system | `code:sandbox:execute` | **是** | -（沙箱自持） | `code` | `code`/`language`/`timeout` | - | 否 |
| `search_resources` | v1 | system | `resource:search` | 否 | -（handler 自持） | `query` | `limit`/`query`/`resource_type` | - | 否 |
| `generate_learning_materials` | v1 | system | `material:generate` | **是** | -（handler 自持） | `topic`/`types` | `description`/`pptx_template`/`topic`/`types` | - | 否 |

角色侧：`planner` 3 键（画像/错题/先修）、`tutor` 1 键（课程证据）、`practice` 与 `reviewer` **有意 0 键 0 工具**（只消费计划已取回的东西）、内部角色 `system` 5 键（V1 全部）。

`decide_access()` 的判定顺序与拒绝分类（deny-by-default：三层任一不 positively 命中即拒）：

| reason | 含义 | 来源层 |
|---|---|---|
| `unknown_tool` | 名字不在目录里 | 目录注册层 |
| `unknown_role` | 角色没有任何权限键（含 `student`/`teacher`/`admin` 等主体角色） | 角色层 |
| `role_not_allowed` | 目录里该工具没列出这个角色 | 工具×角色层 |
| `permission_not_granted` | 角色在工具上被列出、但实际不持有该工具的权限键（矩阵自相矛盾） | 权限键层 |
| `granted` | 三层全部命中 | 放行 |

- **基线是「等值迁移」，不是重新授权**：测试内嵌 221 之前 `ROLE_TOOLS` 的字面 dict，`{role: tools_for_role(role)} == 基线` 与 `matrix_violations() == []` 两条同时断言；越权扫（4 角色 × 9 工具 = 36 对）逐对核对 `decide_access` 的结论与拒绝理由。反向验证 rp02 证明这一层真能咬：把 `get_learning_profile` 的 `allowed_roles` 加上 tutor **并同时**给 tutor 补权限键（两层一致、`matrix_violations()` 仍为空）→ **4 failed / 14 passed**，红点正是基线钉与越权扫。
- **错误面稳定**：六态状态、`ToolResult` 六字段、`audit()` 六键、V1 的 `{success, error, tool}` 三键全部由用例逐字钉住；拒绝与非法参数的 `data` 恒为 `None`、`result_count` 恒为 0；`missing_scope`（空 `user_id`/`course_id`）仍是拒绝而不会退化成更宽的默认范围。
- **审计覆盖拒绝**：221 之前拒绝路径不写任何记录（V1 只有展示用 trace，V2 的 `audit()` 只在返回后才存在）。现在每个结局各写一条统一事件（rp07 把 `finish()` 绕回 221 之前的直接返回 → **3 failed / 15 passed**，红点正是「一调用一事件」与 refused 计数）。事件只存元数据与摘要哈希：rp08 把 `tool` 字段退回空串 → **4 failed / 14 passed**（未登记工具的名称是审计唯一的线索）。

### 27.3 实测（offline，零模型调用，每条日志均记 `CMD:` 与 `PYTEST_EXIT=`，探针 `outbound attempts=0 unique_hosts=0`）

| 量 | 值 | 证据 |
|---|---|---|
| 新文件单跑 | **18 passed / 0 failed / 0.93 s**，`PYTEST_EXIT=0` | `logs/measure-221-newfile.txt` |
| 既有工具面 | `test_agent_tools.py` + `test_v2_learning_tools.py` + `test_mcp_readonly_protocol.py` + 本卡新文件 = **32 passed / 1 skipped / 5.17 s**（前三个文件收集到 14 项，唯一 skip 仍是 `mcp` 未装的 `importorskip`） | `logs/measure-221-tools.txt` |
| 学习包/运行时面 | 5 个文件（学习包、重规划、V2 runs、检索、图安全）**60 passed / 0 failed / 23.77 s** | `logs/measure-221-package.txt` |
| **CI 同形子集（44 文件，未纳入本卡新文件）** | **521 passed / 1 skipped / 0 failed / 4 warnings / 147.78 s**，旗标按 `ci.yml:217` 同形 + `-rs`；与 211c 记录**逐数相同** = 本卡对既有行为零改变 | `logs/measure-221-ci44.txt`、`logs/portable-list.txt` |
| 候选 45 文件清单（**仅证据，未采纳**） | **539 passed / 1 skipped / 0 failed / 4 warnings / 143.83 s**（= 521 + 本卡 18 项） | `logs/measure-221-ci45-candidate.txt`、`logs/candidate-list.txt` |
| **全量（记录数）** | **2410 passed / 0 failed / 20 skipped / 1067.30 s / 23 warnings**（2026-10-24 QWEN-221 最终字节复跑，Windows + Python 3.12.15；口径不变：`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + 全新 `--basetemp output/qwen221-2026-10-24/pytest-measure-221-full-suite`，挂同一个 fail-closed socket 探针，探针 **`outbound attempts=0 unique_hosts=0`**，零计费模型调用、未读 `.env`、无用例因阻断转红，`PYTEST_EXIT=0` 记入日志）＝ **2430 项**（passed + skipped）/ 197 个测试文件 = 211c 的 2412 项 + 本卡新增 18 项；既有 3 个工具文件 14 项与 5 个学习包/运行时文件 60 项在本卡最终字节上全部照旧通过（`32 passed, 1 skipped in 5.17s`、`60 passed in 23.77s`） | `logs/measure-221-full-suite.txt` |
| 集合口径 | `--collect-only -q` 得 **2429** 个 node id，分布在 **196** 个文件（`2429 in 13.35s`）；node id 2429 + 收集期整文件跳过的 `test_mcp_readonly_protocol.py`（本机未装 `mcp` 的 `importorskip`）1 条 = **2430 项**，与全量 passed + skipped 逐数相同；因此全量那一轮实际触达 **197** 个文件（有 node id 的 196 + 那 1 个只贡献收集期 skip 的），与 211c 的 195 + 1 = 196 同口径 | `logs/measure-221-collect-only.txt`、`logs/file-counts.txt`（`files_count_221.py` 两份日志并排取数） |
| 反向验证 | 11 组，**全部 `RED_OK`**（每次只改一处、跑本卡测试文件、按字节恢复并断言 md5 相同；每组都有 pytest summary 行、红点点名用例、无 ImportError、探针 0/0）：rp01 权限键层 5 failed / rp02 两层一致扩权 4 / rp03 工具改名脱登记 5 / rp04 未知角色层 2 / rp05 V1 闸门不看名字 1 / rp06 `extra=ignore` 2 / rp07 拒绝不写审计 3 / rp08 审计丢 attempted 名 4 / rp09 截断回字面量 1 / rp10 MCP 改名 1 / rp11 OpenAI 导出丢 `required` 1；每组都是 `18 = failed + passed` 的完整收集 | `logs/reverse-proofs.txt`（驱动 `reverse_proofs_221.py`，`ALL_PROOFS_VALID=1`） |
| 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed!**（exit 0）、`compileall backend/app tests/` exit 0、CI 前置 `init_db()` INITDB_EXIT=0、`git diff --check` 干净 | `logs/gates.txt`、`logs/ci-init-db.txt` |
| 字节与行尾 | 新目录 215 行 `3c13c4490298567bf34b6986e6c86656`、审计 123 行 `7cb62306d6677cbb980000240b5bab39`、broker 171 行 `e17a28b1da38837f4b983e51b5635233`、V1 注册表 503 行 `8b6844c70c32fd516d9ff4ef62b9693a`、测试 395 行 `af49171bb284a43725e312b8571d8ef2`，全部纯 CRLF（孤立 LF/CR 各 0）；`mcp_readonly.py`、`ci.yml`、`learning_runs.py`、`learning_package.py` md5 未变 | `logs/final-bytes.txt`、`logs/ci-list.txt`、`logs/openai-export-compare.txt`、`logs/baseline-bytes.txt` |
| OpenAI 导出平价 | `HEAD tools=5 NEW tools=5 identical=True`、`ORDER_SAME=True`、`OWNER_SAME=True`、`OPENAI_EXPORT_IDENTICAL=1`（脚本 `git show HEAD:` 取旧版并排比对） | `logs/openai-export-compare.txt`、`tmp/head_registry.py` |

### 27.4 边界与未做

- **角色划分留给产品裁定，本卡只给基线**：矩阵按 221 之前的实际行为等值迁移，`practice`/`reviewer` 零权限、V1 五个工具只给内部角色 `system`（V1 只被进程内产品代码调用，没有能命名角色的外部调用方）都是**现状**而非主张。已在 `[DONE]` 列为待裁定的具体一条：`backend/app/mcp_readonly.py:25` 把范围固定成 `role="planner"`，而 `search_course_evidence` 的基线只给 `tutor`，所以 MCP 侧那个工具名会稳定返回 `denied`——**221 前后一致**（旧 `ROLE_TOOLS` 同样如此），本卡不擅自扩权也不擅自改名，登记待裁。既有 `tests/a/test_mcp_readonly_protocol.py` 的第一条用例注入的是假 broker，因此今天没有任何用例覆盖这一点。
- **两处「声明了但运行时不消费」的 allowed_tools 未合并**：`backend/app/services/agent_config_service.py`（`:38`/`:133`/`:156`，配 `core/models.py:476` 的 JSON 列与 `agents/configurable_agent.py:4`）是持久化配置面，`backend/app/agent_runtime/contracts.py:20` 的 `RunPolicy.allowed_tools`（和 `RunContext.permissions`）目前没有任何消费者。运行时权限判定已统一走目录，这两处属配置/编排层，归后续卡（301/341/343）；`configurable_agent` 不执行工具，故本卡不存在「绕过矩阵」的路径。
- **审计仍是进程内环形缓冲**（500 条、不落库、不经 API 暴露）：满足派工第 2 条「一律拒绝并写审计事件」，但持久化审计要定 schema 与迁移，超出 221「不碰 API/UI」的范围，归 341/343 观测面。
- **超时语义**：V2 四个工具由 broker 统一 `asyncio.wait_for`（标准 10 s、检索 30 s，值从 spec 派生）；V1 五个工具 `timeout_seconds=None` 表示由 handler 自己持有（`execute_code` 的沙箱 `timeout` 参数），不是缺失。截断配额目前只有 `search_course_evidence` 的 5 条进目录；图内另有的 `hits[:5]`/`evidence[:15]` 编排层截断不在 221 范围。
- **CI 快清单未改**（派工没有 CI 条款，按 201b/202b/211b 的先例那是独立一张卡）：44 文件同形复跑仍 **521/1** 就是「既有行为零改变」的证据；45 文件候选 **539/1** 只作采纳前的预演，顺序见 `logs/candidate-list.txt`。
- **未跑 GitHub `quality` job 真实回执**（本机无 `gh`，属 remote 证据、由 Lead 判读）；**未跑 PG `enterprise-contract` 38 文件清单**（本卡零 PG 面改动，同 §22/§23/§25/§26 口径）。
- **迭代与作废记录保留、不掩盖**：`logs/dev-new-permissions.txt` 是用例首稿的三轮迭代（首稿 3 处自身断言写错：`recent()` 是最新在前而非最旧、`by_status` 的 denied 数漏算 `missing_scope`、`ast` 只扫了模块顶层而漏掉 `create_server()` 里嵌套的装饰函数）；`logs/void-full-suite-stopped-midrun.txt` 是 16→18 项之间启动的全量跑，**主动中止、不作记录**；`logs/reverse-proofs.txt` 与四个 `measure-221-*.txt` 都在最终字节上重跑覆盖。
- **文档脚本的首跑在写完文件之后才炸**，如实登记：`apply_docs_221.py` 第一次跑时，前四处改动（台账 §27、矩阵 §24、README `:56`/`:58`）都已落盘，到「评委导览计数格」那条 `assert old_body in after[index]` 才失败——那条断言只该用在「保留同格历史」的格子上，计数格是**故意**整体替换的。处置：五份文档全部从改动前的备份（`tmp/docs-before/`，md5 逐一比对一致、`git status --short` 回到只有 5 个 backend/tests 条目）恢复后重跑，脚本把该断言改为仅 `keep_history` 时生效；恢复过程中我自己在仓库根留下了 4 份同名副本（一条写错的 `cp` 列表），已删除、未进任何提交。
- 计数一律按 pytest summary 行取数；warnings 数随轮次波动不作结论（本轮 CI 子集 4 warnings，与 211c 同数）。
- 证据等级：**offline**。全部为同机同形复跑归档日志；GitHub 回执与 PG 层不属本卡主张。

## 28. QWEN-221b MCP scope 角色回归 + 权限测试进 CI 快清单（2026-10-24，分支 `qwen/wave2-tools`，零模型调用、产品零改动）

**派工与撤回（两版，按后一版执行）**：Lead 2026-10-24 18:30 §4 先派 221b 要求把 `backend/app/mcp_readonly.py` 的 scope role 由 `planner` 改成 `tutor`，并补测试 + CI 44→45；同日 19:35 `[CORRECTION]` **撤回角色修改**：「我上一版 §3-78 读漏了 `backend/app/mcp_readonly.py:56-64`：`search_course_evidence` **已经**用 `tutor_scope` 调用；`planner` scope 只用于 `get_learning_profile`/`get_recent_mistakes`/`get_prerequisites`。所以不存在『MCP 搜索稳定 denied』的 bug，把全局 scope role 改成 tutor 反而会弄坏 planner 的三个工具。」更正版范围逐字：「不改产品权限/角色，只做两件事：① 补 fake-broker/ast 回归测试，证明 MCP `search_course_evidence` 用 `tutor` scope、profile/mistakes/prereqs 用 `planner` scope（本机无 `mcp` 时保持 `importorskip`）；② 把 `tests/a/test_tool_registry_permissions.py` 加入 `ci.yml` 快清单 44→45，预期 **539/1**，更新 README/TEST_MATRIX；零模型、不碰 API/UI；完成后 `[DONE]`。随后 **231**。」本卡从 `qwen/wave2-tools` 起点开工（`main`=`ec29cf4`、分支 HEAD=`9c926ce`，即 Lead 那条 `docs(collab)` 更正提交；`git diff --stat main...HEAD` 只有该文档）。

### 28.1 改动（2 个代码/CI 文件 + 4 个文档文件；产品 `mcp_readonly.py` 零改动）

| 文件 | 改动 | 锚点与字节 |
|---|---|---|
| `tests/a/test_tool_registry_permissions.py` | 用例项 **18 → 18（0 新增）**：把原「MCP 适配器暴露的名字/入参名」用例扩成 MCP scope 角色回归。**静态半**（`ast`，不 import 产品模块）：`_scope()` 内 `ToolContext(..., role=...)` 字面量恒 `planner`、`search_course_evidence` 内恒 `tutor`，search 把 `tutor_scope` 交给 `broker.call(..., "search_course_evidence", ...)`，三个 planner 工具各 `_call("<自身工具名>", ...)`。**动态半**：`sys.modules` 注入假 `mcp`/`mcp.server` 后 `importlib` 导入适配器（保留其 import 期 `RuntimeError` 依赖检查），用录制 broker 跑全部四个工具，`(role, tool)` 序列 = `("tutor","search_course_evidence")` + `("planner","get_learning_profile"/"get_recent_mistakes"/"get_prerequisites")`，run/user/course 三标识全程一致、`knowledge_point_id` 原样转发；并断言 `decide_access("tutor","search_course_evidence").allowed is True` / `planner` 为 `False`。假 `mcp` 只在用例内存在（`monkeypatch.setitem` 撤销、适配器模块 `sys.modules` 条目显式还原），因此全量跑序中 `test_mcp_readonly_protocol.py` 的 `importorskip("mcp")` 行为不变 | 506 行、纯 CRLF（孤立 LF/CR 各 0）、md5 `b3490549e9d41d129fffdc6109b215e7`、`git diff --numstat` **119 / −8** |
| `.github/workflows/ci.yml` | `quality` job portable 快清单 **44 → 45 个文件**：在 `tests/a/test_learning_package_replan.py` 后加 `tests/a/test_tool_registry_permissions.py`（新行 `:217`，旗标行 `--no-cov --benchmark-disable -q` 顺延 `:218`）；`enterprise-contract` 仍 **38**、MCP 协议独立步骤仍保留 | 346 行、纯 CRLF、md5 `13d24bab8fe451d3121de6b4efc4ad20`、`git diff --numstat` **1 / 0** |
| `README.md` | `:58` CI 行换成本卡 45 文件 **539/1** 记录、221 那轮降为同格「再前」；`:56` 全量行换成本卡最终字节复跑记录、221 那轮降为同格「再前」 | `:56`、`:58` |
| `docs/TEST_MATRIX.md` | 新增 §25（**追加**，不回改 §1–§24） | — |
| `docs/CLAIMS_LEDGER.md` | 新增本节 §28（**追加**，不回改 §1–§27） | — |
| `docs/QWEN_LEAD_DIALOGUE.md` | §4 末尾追加本卡 `[DONE]`；§0/§2/§3 **未动**（Lead 维护） | — |

**本卡零改动**：`backend/app/mcp_readonly.py` —— 70 行、md5 `6eea05e5fef4622ae314f9e1e1654e03`（= §27.1 记录的 221 交付值；`git diff HEAD -- backend/app/mcp_readonly.py` 为空；反向验证脚本每次破坏后都按字节恢复并复核 md5，见 28.4）。上述「与 HEAD 相同」沿用 §27.1 的三条判据（工作树 md5 = 前轮记录值、`git diff` 为空、EOL 归一化后与 `git show HEAD:` 同 blob），本机存 LF / 检出 CRLF 的差异不再误读。

### 28.2 角色事实与钉法（为什么两条腿都要）

`mcp_readonly.py` 的现状（**正确**，不改）：`_scope()`（`:19-25`）从环境变量取 run/user/course 并固定 `role="planner"`，服务 `get_learning_profile`/`get_recent_mistakes`/`get_prerequisites` 三个只读工具；`search_course_evidence`（`:56-64`）在函数内另建 `ToolContext(role="tutor")` 再调 broker——因为目录矩阵里 `search_course_evidence` 的允许角色只有 `tutor`，而 `planner` 的权限键只有画像/错题/先修。

- **只用 ast 不够**：ast 钉住「源码今天这样写」，但挡不住未来把 `tutor_scope` 建成后又被误传成 `scope` 之类的运行时接错。
- **只用假 broker 不够**：假 broker 钉住「运行时实际递出去的角色」，但如果导入期 `mcp` 缺失会整条用例不可用；而且不解释「为什么必须是 tutor」。
- 所以本卡两条腿都上：假 `mcp` 注入让动态半在本机无 SDK 时也能跑；`decide_access` 的断言把「tutor 该放行 / planner 该拒绝」的矩阵依据钉在同一处；ast 半则在 import 出问题前就能给出定位。**无 `mcp` 的既有行为保留**：`test_mcp_readonly_protocol.py` 不动，仍整文件 `importorskip`（本机 `SKIPPED ... could not import 'mcp'`），本卡不装依赖。

### 28.3 实测（offline，零计费模型调用；日志均含 `CMD:` 与 `PYTEST_EXIT=`）

| 量 | 值 | 证据 |
|---|---|---|
| 本卡文件单跑 | **18 passed / 0 failed / 1.04 s**，`PYTEST_EXIT=0` | `logs/target-permissions.txt` |
| 定向 4 文件（本卡 + 两个工具面 + MCP 协议） | **32 passed / 1 skipped / 2.67 s**（唯一 skip = `test_mcp_readonly_protocol.py:11` 的 `mcp` `importorskip`） | `logs/target-tools-bundle.txt` |
| **CI 同形子集（45 文件）** | **539 passed / 1 skipped / 0 failed / 4 warnings / 121.79 s**，旗标按 `ci.yml:218` 同形 `--no-cov --benchmark-disable -q -rs` + 前置 `init_db()`；= 44 文件 521 + 该文件既有 18，与 Lead 预计 **539/1** 逐数一致；唯一 skip = `test_auth_restart.py:18` | `logs/ci45.txt`、`logs/portable-list.txt`、`logs/ci-list-inspect.txt` |
| **全量（记录数）** | **2410 passed / 0 failed / 20 skipped / 20 warnings / 893.78 s / `PYTEST_EXIT=0`**，197 个测试文件 / **2430 项**；与 221 记录 2410/0/20 **逐项相同**（0 新增用例项、产品零改动），warnings 数随轮次波动（221 记录 23 条、本轮 20 条）不作结论 | `logs/full-suite.txt` |
| 集合口径 | `--collect-only -q` = **2429** node id + 收集期 1 条 `mcp` `importorskip` = **2430 项**（14.90 s），与 221 同口径 | `logs/collect-only.txt` |
| 清单机械重取 | `inspect_ci_list_221b.py` 用 `yaml.safe_load` 读 `ci.yml`：portable **45** 条、无重复、0 缺失、末位即本卡文件；`enterprise-contract` **38**；MCP 协议步骤仍在 | `logs/ci-list-inspect.txt`（`CI_LIST_OK=1`） |
| 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed!**（exit 0）、`git diff --check` 干净、CI 前置 `init_db()` INITDB_EXIT=0 | `logs/gates.txt` |
| 字节 | 测试 506 行 `b3490549e9d41d129fffdc6109b215e7`、`ci.yml` 346 行 `13d24bab8fe451d3121de6b4efc4ad20`，均纯 CRLF 孤立 LF/CR 各 0；`mcp_readonly.py` md5 未变 | — |

### 28.4 反向验证（4 组，全部 `RED_OK`，破坏后按字节恢复）

脚本 `output/qwen221b/reverse_proofs_221b.py`（未进仓库，`output/` 已被 `.gitignore` 忽略）：每组只改 `mcp_readonly.py` 一处，跑本卡测试文件，记录 summary，再从备份按字节恢复并断言 md5 回到 `6eea05e5fef4622ae314f9e1e1654e03`。

| 组 | 单层破坏 | 结果 |
|---|---|---|
| rp01 | `_scope` 的 `role="planner"` → `"tutor"` | **1 failed / 17 passed**（`RED_OK=1`） |
| rp02 | search 的 `role="tutor"` → `"planner"` | **1 failed / 17 passed** |
| rp03 | search 改把 base `scope` 交给 broker（而非 `tutor_scope`） | **1 failed / 17 passed** |
| rp04 | `get_recent_mistakes` 转发成 `get_learning_profile` | **1 failed / 17 passed** |

收尾：`RESTORED_MD5=6eea05e5fef4622ae314f9e1e1654e03 MATCH=1`、`GIT_DIFF_EMPTY=1`、`ALL_PROOFS_VALID=1`（`logs/reverse-proofs.txt`）。

### 28.5 边界与未做

- **539 的口径**：Lead 预期 539 = 44 文件 521 + 本卡文件既有 18。本卡按 107b/107c 的既有先例**扩展既有用例、不新增用例项**（否则 45 文件清单会变成 539 + 新增数），所以 18 → 18、清单仍是 539/1。若 Lead 希望 MCP 角色回归是独立用例项，可另开小卡（会让 CI 计数再 +N）。
- **未挂 fail-closed socket 探针**：本轮只显式设 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none`、用隔离 SQLite 与全新 `--basetemp`、未读 `.env`、未新增任何网络依赖；因此**不主张** `outbound attempts=0 unique_hosts=0` 探针值（前几卡的探针脚本未随仓库管理）。零计费仍由离线开关与改动面（测试 + CI 清单 + 文档）共同支撑。
- **未跑 GitHub `quality` job 真实回执**（本机无 `gh`，属 remote 证据、由 Lead 判读）；**未跑 PG `enterprise-contract` 38 文件**（本卡零 PG 面改动，同 §22–§27 口径）。
- **§2 任务板第 75 行仍是撤回前的旧描述**（「`mcp_readonly.py` 角色 planner→tutor」），与 §3-78/79 更正及实际代码矛盾。本卡无权改 §0/§2/§3（Lead 维护），已在 `[DONE]` 中提请 Lead 更新；本卡落地的是更正版范围。
- **起点事实按 git 记录**：开工时 `main`=`ec29cf4`、`qwen/wave2-tools`=`9c926ce`（比 `main` 多一条 Lead 的 `docs(collab)` 更正提交；`git diff --stat main...HEAD` 只有 `docs/QWEN_LEAD_DIALOGUE.md`），working tree clean。Lead 口述的「main = 9c926ce」与 `git log` 不符，以代码事实为准。
- **未动 QWEN-231**：按指令完成即停、hold 等验收。
- 证据等级：**offline**。全部为同机同形复跑归档日志；GitHub 回执与 PG 层不属本卡主张。

## 29. QWEN-231 统一 Observation + 交付前规则版 claim-support（2026-10-24，分支 `qwen/wave2-observation`，零模型调用）

Lead §4（`[2026-10-24 20:05]`）派工逐字：「(a) 统一 `Observation` schema：状态（success/partial/failed 等）、错误类、是否可重试、证据强度/引用支持度；接入学习包观察/交付路径，保持既有事件与错误码兼容；(b) V2 交付前最多一次 **claim-support 二次校验**，默认规则版、不额外付费；校验失败→**不交付或返工**（沿用既有 Reviewer 路径），并写审计；测试覆盖通过/失败/返工/引用不足；零模型、不碰 API/UI/前端；完成后 `[DONE]` 附 schema、失败路径与审计证据。之后 **301**。」

### 29.1 改动（3 个产品/评测文件 + 1 个新测试文件 + 1 个既有测试文件 + 7 个文档文件）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `backend/app/agent_runtime/observation.py`（新） | 统一 `Observation` Pydantic schema：`node` / `status`（success/partial/failed/skipped）/ `error_class` / `retryable` / `evidence_strength`（0..1）/ `citation_support`（0..1）/ `detail`（只放计数与稳定 code）；`classify_failure()` 把既有错误码映射为 `(error_class, retryable)`；`failure_observation()` 不写异常文本 | `:36`（`class Observation`）、`_FAILURE_POLICY`（`:18`） |
| `backend/app/agent_runtime/learning_package.py` | `PackageState` 新增 `claim_support` / `claim_support_checked` / `delivery_observations`；`_observed` 在节点失败时发 `observation.recorded`、成功时把 `_observation_events` 并入 `delivery_observations` 并发同一事件；`_tool` 把每次检索投影成 Observation（不替换既有 `observations` 载荷）；新增 `claim_check` 节点（compose → claim_check → approval/verify）；`_claim_check` 只读规则校验、`claim_support_checked` 保证每运行最多一次；失败 fail-closed 沿用 `learning_package_invalid_citation` / `learning_package_quality_failed`；`quality` 增加 `claim_support` 与 `delivery_observations`；人工替换清空两者 | `:25`（`PROMPT_VERSION` 仍 v2.9）、`:802`（`_claim_check`）、`:292`（compose→claim_check 边） |
| `backend/app/evaluation/claim_support.py` | 新增纯规则 `evaluate_rule_based_support(items, evidence)`：引用 ID 必须全部指向本次检索证据且内容非空；证据文本 ≥40 字符时用字符二元组重叠判断词面支持；支持率 <0.5 或任一缺失/非法引用即失败；短证据（<40 字符）标为“未判定”，避免对既有小 fixture 编造结论 | `:87-88`（`MIN_EVIDENCE_CHARS=40` / `MIN_SUPPORT_RATE=0.5`）、`:102`（函数） |
| `tests/a/test_observation_claim_support.py`（新） | **10 项**：Observation schema/错误分类、通过路径、支持不足→不交付+checkpoint、引用不足→citation 失败观察、既有 Reviewer 返工仍交付且只查一次、失败后零额外模型调用、既有事件不被替换、人工替换清空模型侧结论、数值边界/JSON 序列化 | — |
| `tests/a/test_claim_support.py` | **9 → 13 项（+4）**：规则版通过、长证据不支持、缺失/非法引用、短 fixture 不判定 | — |
| `docs/CLAIMS_LEDGER.md` | 本节 §29（追加） | — |
| `docs/TEST_MATRIX.md` | §26（追加）+ 文件矩阵新增一行 | — |
| `docs/LEARNING_PACKAGE_GUIDE.md` | 事件与 `quality` 新字段说明 + 规则版 claim-support 边界 | `:88-89`、`:104` |
| `docs/V2_TEN_MODULE_IMPLEMENTATION.md` | `PROMPT_VERSION` 行号 `:23`→`:25`（新增两行 import 后移；版本值未变） | `:58` |
| `README.md` / `docs/00-评委30秒导览.md` | 全量计数刷新；CI 快清单未改 | `:56`、`:58` / `:106` |
| `docs/QWEN_LEAD_DIALOGUE.md` | §4 末尾 `[DONE]`；§0/§2/§3 未动 | — |

**未改**：`PROMPT_VERSION` 仍 `learning-package-v2.9`（本卡没有新增模型可见固定文本；`claim_check` 是纯规则、失败即停，不向模型追加 Reviewer 反馈）；`.github/workflows/ci.yml`、API/UI/前端/迁移/容器一律未动。

### 29.2 Observation 的统一口径

- `status` 四态：`success` / `partial` / `failed` / `skipped`；失败观察的 `error_class` 来自既有错误码映射，未知码归 `runtime`。
- `retryable` 只表示**既有有界恢复路径**能否在不换请求的情况下重试：`invalid_output`、`tool_failed`、`repeated_search` 为 `true`；预算、无证据、授权拒绝、质量失败、引用失败为 `false`。
- `evidence_strength` / `citation_support` 均为 0..1；检索观察暂不填这两项（只给 `result_count` / `valid_count` / `evidence_count`），claim-support 观察填实际值。
- 每次 `observation.recorded` 都落 `agent_checkpoints`（`node_name` = 观察的 `node`），SSE 与审计读取同一份数据；既有事件名、错误码、checkpoint 结构和 `learning_package` 交付形状不变。

### 29.3 claim-support 二次校验（为什么选“不交付”）

- 校验点在 `compose` 之后、人工审核/`verify` 之前，读的是**最终要交付的** `learning_package`（部分交付时只含实际交付的 lesson/exercises）。
- `claim_support_checked` 让每运行最多执行一次；失败直接抛既有稳定错误码，**不新增重试、不重复调用 Reviewer、不增加模型/工具预算**。既有 Reviewer 的“一次有界返工”路径保持原样（`test_existing_reviewer_rework_delivers_after_one_support_check` 钉住）。
- 引用不足 → `learning_package_invalid_citation`；证据词面支持不足 → `learning_package_quality_failed`；两种都在 `observation.recorded` 里带 `error_class=citation|claim_support`、`retryable=false`，且 `answer.delta` 不出现。
- 既有引用校验（`_check_sources`）仍是第一道；本卡是交付前的第二道规则兜底，不替代人工审核。

### 29.4 实测（offline，零计费模型调用）

| 量 | 值 | 证据 |
|---|---|---|
| 本卡新文件单跑 | **10 passed / 0 failed / 7.16 s**，`PYTEST_EXIT=0` | `output/qwen231/logs/new-file.txt` |
| 定向 5 文件（新文件 + `test_claim_support` + `test_learning_package` + `test_learning_package_replan` + `test_learning_package_partial`） | **96 passed / 0 failed / 60.92 s**，`PYTEST_EXIT=0` | `output/qwen231/logs/targeted.txt` |
| 相关面（collection/evaluator/structured_output/ablation/lifecycle/retry_guidance/reconciliation） | **150 passed / 0 failed / 38.77 s**，`PYTEST_EXIT=0` | `output/qwen231/logs/related.txt` |
| 全量 `pytest tests/` | **2424 passed / 0 failed / 20 skipped / 24 warnings / 1431.51 s (0:23:51)**，`PYTEST_EXIT=0`，198 个测试文件 / **2444 项** | `output/qwen231/full-suite.txt` |
| 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` + `git diff --check` | **RUFF_EXIT=0（All checks passed）；DIFFCHECK_EXIT=0**（仅 CRLF 归一化 warning） | `output/qwen231/logs/ruff.txt`、`output/qwen231/logs/gates.txt` |
| CI 快清单 | 未改 `ci.yml`，仍 45 文件；`test_claim_support.py` 规则用例 +4 → **543 passed / 1 skipped / 0 failed / 4 warnings / 288.83 s**，`CI45_EXIT=0`；新测试文件未纳入 | `output/qwen231/logs/ci45.txt` |

### 29.5 边界与未做

- 规则版是**词面启发式**：字符二元组重叠只能说明“可能相关”，不证明语义蕴含；短证据（<40 字符）不判定；支持率阈值 0.5 是基线常量，可在后续卡按产品需要调整。
- **未新增付费模型调用**、未读 `.env`、未安装依赖；本轮**未挂 fail-closed socket 探针**，故不主张 `outbound attempts=0` 探针值；零计费由 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none` 与改动面（纯规则/测试/文档）共同支撑。
- **未跑 GitHub `quality` 真实回执**（remote 证据，由 Lead 判读）；**未跑 PG `enterprise-contract`**（本卡零 PG 面改动）。
- **未把新测试文件加入 `ci.yml` 快清单**：沿用 201b/202b/211b/221b 的“CI 纳入另卡”先例；本卡未改 CI。（本条由 **QWEN-231b** 关闭，见 §30。）
- **未做反向验证**：本轮以正向通过 + 失败路径用例（支持不足/引用不足/失败即停）作为证据；若 Lead 要求反向破坏证明，可另开小卡或在本卡补跑后再验收。
- **“最多一次”的边界**：`claim_support_checked` 在通过时写入检查点，单次执行内不会重复；失败的 run 停在 `claim_check`，显式 `/{run_id}/continue` 只重放该节点一次，属新的执行尝试，仍不会形成内部重试循环。
- 未动 QWEN-301；完成 231 即停，hold 等验收。
- 证据等级：**offline**。

## 30. QWEN-231b Observation 测试纳入 CI 快清单（2026-10-24，分支 `qwen/wave2-observation`，零模型调用、产品与测试逻辑零改动）

Lead §4（`[2026-10-24 21:45]`）派工逐字：「把 `tests/a/test_observation_claim_support.py` 加入 `ci.yml` 快清单 45→46，预期 **553/1**；更新 README/矩阵计数；只改 CI/文档；完成后 `[DONE]`。」

### 30.1 改动（1 个 CI 文件 + 3 个文档文件）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `.github/workflows/ci.yml` | `quality` job portable 快清单 **45 → 46 个文件**：在 `tests/a/test_tool_registry_permissions.py` 后加 `tests/a/test_observation_claim_support.py`（新行 `:218`，旗标行 `--no-cov --benchmark-disable -q` 顺延 `:219`）；`enterprise-contract` 仍 **38**、MCP 协议独立步骤仍在 | `:218` |
| `README.md` | `:58` CI 行换成本卡 46 文件 **553/1** 记录，231 的 543/1 降为同格「再前」 | `:58` |
| `docs/TEST_MATRIX.md` | 文件矩阵 `test_observation_claim_support.py` 行补 `F` 标记并更新备注；新增 §27（追加） | `:103`、§27 |
| `docs/CLAIMS_LEDGER.md` | §29.5「未把新测试文件加入快清单」条目标注由本卡关闭；新增本节 §30（追加） | — |

**未改**：任何 `backend/`、`tests/`、`scripts/` 文件；`PROMPT_VERSION`、产品逻辑、测试逻辑一字未动。

### 30.2 实测（offline，零计费模型调用）

| 量 | 值 | 证据 |
|---|---|---|
| 清单机械重取 | `yaml.safe_load` 读 `ci.yml`：portable **46** 条、无重复、0 缺失、末位即本卡文件 | `output/qwen231b/logs/portable-list.txt` |
| 前置 `init_db()` | exit 0（全新 `output/qwen231b/ci.db`） | — |
| **CI 同形子集（46 文件）** | **553 passed / 1 skipped / 0 failed / 4 warnings / 281.02 s (0:04:41)**，`CI46_EXIT=0`；= 231 记录的 543/1 + 该文件既有 **10** 项，与 Lead 预计 **553/1** 逐数一致；唯一 skip 仍是 `test_auth_restart.py:18` | `output/qwen231b/logs/ci46.txt`、`ci46-exit.txt` |
| 门 | `git diff --check` | exit 0（仅 CRLF 归一化 warning） |
| 全量 | **未重跑**：本卡 0 新增用例项、产品零改动，记录数仍为 231 的 **2424/0/20 / 2444 项** | §29.4 |

### 30.3 边界与未做

- 本卡只改 CI/文档，零模型调用、未读 `.env`、未装依赖、未跑探针（不主张 `attempts=0` 探针值）。
- **未跑 GitHub `quality` 真实回执**（remote 证据，由 Lead 判读）；全量与 PG 面未重跑（本卡零产品/零用例项改动，记录数不变）。
- 随后开工 QWEN-301（`qwen/wave3-queue`）。
- 证据等级：**offline**。

## 31. QWEN-301 Run 队列/Worker：创建与执行解耦、租约、取消/超时与崩溃恢复（2026-10-24，分支 `qwen/wave3-queue`，零模型调用）

Lead §4（`[2026-10-24 21:45]`）派工逐字：「Run 创建与执行解耦；Worker 租约领取/心跳/取消/超时；崩溃后租约过期可重领；创建返回可查询 ID、API 兼容；**不声称 exactly-once**；测试覆盖跨进程领取/心跳/取消/超时/杀进程恢复；零模型、不碰 UI。」

### 31.0 一页方案（实现前定稿的架构选择）

- **队列载体**：**不新增表/列、零迁移**。入队态就是 `agent_runs.status='queued'`，队列簿记（`enqueued_at` / `attempts` / `worker_id` / `claimed_at` / `retired_by`）放在既有 `metadata` JSON 的 `queue` 键里。理由：复用 `run_leases` 已验证的行级原子 UPDATE 模式，避免迁移风险；`agent_checkpoints` 上既有的 `uq_checkpoint_run_sequence (run_id, sequence)` 唯一索引天然提供事件序号防重。
- **状态机**（全部持久化在 run 行上）：
  `queued ─claim→ running ─finish→ completed / partially_completed / awaiting_approval / failed`；
  `queued ─cancel→ cancelled`；`running ─cancel（同事务轮换 execution_id、清租约）→ cancelled`（旧 Worker 的下一次 fenced 写失败，不覆盖取消结果）；
  `running/interrupted 且租约过期 ─claim→ running`（at-least-once 重领，`attempts+1`）；
  `attempts > MAX_ATTEMPTS(=2)` 的那次领取**不再执行**，直接判 `failed("run_queue_attempts_exhausted")`（新增的队列专属稳定码，不触碰既有错误面）。
- **Worker**：`run_worker.work_once / work_forever`。领取（`run_queue.claim_next_run`）→ 用与 `/stream` **同一**运行时（`learning_runs._graph / _package_graph`，同 `ingestion.py` 复用既有管道的先例）执行 → `run_leases.renew` 心跳（读调用点属性，可测试注入）→ `asyncio.wait_for` 超时（answer 60s / package 180s，同 `/stream`）→ `run_audit.log_retrieval` → `run_lifecycle.apply_settled_state` → 有守卫的 finish（fence + `status=='running'`）。**不**复用 `finish_run(expected_status=...)`（它固定写 `run.reconciled` 审计行，语义属 reconcile）。
- **API**：新增 `POST /api/v2/learning-runs/enqueue`（返回 `run_id` + `status='queued'`，不执行；package 模式同样要求登录、builder 可用）与 `POST /{run_id}/cancel`（仅 `queued/running` 且**队列来源**的 run 可取消；`409 run_not_cancellable` / `409 run_not_queued`）。既有 `/stream`（保留同步语义，同 ingestion 同步端点先例）、`GET /{run_id}`、`/resume`、`/continue`、`/reconcile` 一字未改。
- **语义**：**at-least-once**。崩溃后任一 Worker 的领取扫描会重领（`queued`、`running` 租约过期、`interrupted` 三类候选；只认队列来源，不劫持 legacy run 的 `/continue`+reconcile 路径）；死亡执行的新写被轮换后的 `execution_id` fence 拒绝。不声称 exactly-once。
- **SQLite 并发细节**：SQLite 的 `SELECT ... FOR UPDATE` 不锁行，取消者/僵尸 Worker 与另一写者可能抢同一事件序号，输家撞 `uq_checkpoint_run_sequence`（IntegrityError）——`run_queue._safe_write_retrying` 对 IntegrityError 有界重试 3 次（PG 有真行锁，重试无害）；这是本轮实测发现的真问题，已按最小修复收口。

### 31.1 改动（3 个产品/运行时文件 + 1 个新测试文件 + 1 个测试探针 + 5 个文档文件）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `backend/app/agent_runtime/run_queue.py`（新，172 行） | 队列状态机：`claim_next_run`（单条件 UPDATE 定胜者、DB 时钟 `session.scalar(select(db_now))` 一次取值、`attempts` 赢取后从新鲜 metadata 自增）、`cancel_run`（queued/running 两路、running 路轮换 `execution_id`）、`_retire_exhausted`（同事务判失败 + `run.queue_exhausted` 审计）、`is_queued_run` / `queue_origin`（队列来源判定）、`_safe_write_retrying`（SQLite 序号竞争重试）；常量 `MAX_ATTEMPTS=2`、`ATTEMPTS_EXHAUSTED="run_queue_attempts_exhausted"`、`QUEUE_STATUSES` | — |
| `backend/app/agent_runtime/run_worker.py`（新，174 行） | `work_once`（claim→执行→settle→守卫 finish，返回稳定 outcome：`idle`/终态 status/`cancelled`/`lost_lease`/`missing`/`persistence_unavailable`）、`work_forever`（持久化故障睡眠重试不退出）、`_execute_claimed`（与 `/stream` 同构：history/画像加载、on_event 落 `agent_checkpoints`、心跳任务 + `asyncio.wait_for` 超时；心跳失败传播并取消图任务）、`_finish_guarded`（fence + `status=='running'` 守卫 + 终态事件映射，无 `run.reconciled` 污染） | — |
| `backend/app/agent_runtime/run_audit.py` | 新增 `queue_run(...)`：与 `start_run` 同构的行，但 `status='queued'`、无租约、初始审计 `run.queued`；`start_run`/既有函数一字未动 | `:85` |
| `backend/app/api/v2/learning_runs.py` | 新增 `POST /enqueue`（401/503 语义同 `/stream`；返回 `{run_id, status:'queued', session_id, workflow_version}`）与 `POST /{run_id}/cancel`（409 码稳定）；新增 `import time`、`run_queue`；既有端点与 `/stream` 行为一字未动 | `:270`、`:306` |
| `tests/a/test_run_queue.py`（新，**15 项**） | 见 31.2 | — |
| `tests/helpers/run_queue_probe.py`（新） | 跨进程 Worker 探针：argv `sqlite路径 mode(hang|quick)`，import 前 set `DATABASE_URL`，离线桩运行时，禁外联（`httpx`/`requests` patch），stdout 输出 JSON outcome | — |
| `docs/CLAIMS_LEDGER.md` | 本节 §31（追加） | — |
| `docs/TEST_MATRIX.md` | 文件矩阵新增一行（`test_run_queue.py`，N 列 ✓、未进 fast）+ 新增 §28 | — |
| `docs/LEARNING_PACKAGE_GUIDE.md` | 新增「队列执行（QWEN-301）」小节：enqueue/cancel 契约、at-least-once 语义、`/stream` 不变 | — |
| `README.md` | `:56` 全量行、`:58` CI 行（CI 清单未动、计数不变，注明 301 字节上复跑） | `:56`、`:58` |
| `docs/00-评委30秒导览.md` | 测试用例行更新 | `:106` |
| `docs/QWEN_LEAD_DIALOGUE.md` | §4 末尾追加 `[DONE]`；§0/§2/§3 未动 | — |

**未改**：`run_lifecycle.py`、`run_leases.py`、图/学习包逻辑、`ci.yml`、迁移/表结构（**零迁移**）、前端/UI。`WORKFLOW_VERSION` 与 `PROMPT_VERSION` 未动（无图状态格式变更、无提示词变更）。

### 31.2 测试覆盖（15 项，全部离线；scripted/stub 运行时 + 隔离 SQLite + 全新 basetemp）

| 用例 | 覆盖点 |
|---|---|
| `test_enqueue_returns_queryable_queued_run` | 创建/执行解耦：enqueue 只落 `queued` 行（无租约、无 `run.started`、有 `run.queued`），GET 可查询，`/stream` 同 app 内仍正常 |
| `test_enqueue_package_mode_requires_login` | enqueue 的 401 错误面与 `/stream` 一致 |
| `test_worker_claims_and_completes_run` | 正常领取→执行→交付：`run.claimed(attempts=1)`、retrieval 审计行、`run.completed`、`success_count=1`、无 `run.reconciled` 污染、二次 work_once `idle` |
| `test_two_workers_never_double_claim` | 双线程并发领取：胜者 completed、败者 idle、attempts==1 |
| `test_heartbeat_renews_lease_during_execution` | 心跳：`run_leases.HEARTBEAT_SECONDS` 注入 0.05s，执行 0.5s，renew ≥3 次，完成后状态 completed |
| `test_timeout_marks_run_failed` | 超时：`timeout_seconds=0.2` + 5s 慢生成 → `failed` + `{"error":"run_timeout"}`（复用 `/stream` 的既有码）+ 租约释放 |
| `test_cancel_queued_run_is_never_claimed` | 排队取消：`cancelled` 行永不被领取、result `{"cancelled": True}`、`run.cancelled` 审计 |
| `test_cancel_running_run_fences_the_worker` | 运行中取消：取消后 Worker 的检索日志/finish 全被 fence，outcome=`cancelled`，终态保持 cancelled 且不被 Worker 覆盖 |
| `test_cancel_conflicts_are_stable` | 完成态取消 409 `run_not_cancellable`；legacy（`/stream` 形状）running run 取消 409 `run_not_queued` |
| `test_expired_lease_can_be_reclaimed_by_another_worker` | 租约过期重领：attempts 1→2、新 `execution_id`；旧执行的 `renew` 被 fence 拒绝（RunStateConflict），新执行可续 |
| `test_attempts_exhausted_fails_the_run` | 上限：第 3 次领取不再执行，`failed("run_queue_attempts_exhausted")` + `run.queue_exhausted(attempts=3)` 审计 |
| `test_legacy_interrupted_run_is_not_reclaimed` | 不劫持：legacy interrupted run 不被队列领取，`/continue`+reconcile 语义保留 |
| `test_live_zombie_worker_cannot_publish_after_reclaim` | 僵尸隔离：被重领后活着的旧 Worker 无法交付（outcome=`lost_lease`），最终由新 Worker 唯一 `run.completed`，attempts==2 |
| `test_killed_worker_process_is_reclaimed_and_completed` | **杀进程恢复（跨进程）**：subprocess 探针 hang→领取→父进程 `kill()`→强制租约过期→第二个探针进程重领并完成；attempts==2、`run.claimed×2`（probe-hang→probe-quick）、唯一 `run.completed`、API 可查询 |
| `test_queued_package_run_reaches_review_and_teacher_resume` | API 兼容：队列来源的 package run 经 Worker 到 `awaiting_approval`（学生视图 `review_required`、教师视图 approval 草稿），教师 `/resume` 原端点完成交付——`/resume` 对队列 run 零改动可用 |

### 31.3 实测（offline，零计费模型调用；日志均含 `*_EXIT=`）

| 量 | 值 | 证据 |
|---|---|---|
| 新文件单跑 | **15 passed / 0 failed / 19.88 s**，`NEW_FILE_EXIT=0` | `output/qwen301/logs/new-file.txt` |
| 稳定性复跑 | 同文件连续 3 轮 **15 / 15 / 15 passed**（20.16 s / 19.55 s / 20.29 s） | `output/qwen301/`（base-stab1..3） |
| 定向相关面（10 文件：run_leases/lifecycle/learning_runs_v2/reconciliation/learning_package/partial/observation/unfinished_resume/event_idempotency/checkpoint_lifecycle） | **137 passed / 0 failed / 84.79 s**，`RELATED_EXIT=0` | `output/qwen301/logs/related.txt` |
| **CI 同形子集（46 文件，清单未改）** | **553 passed / 1 skipped / 0 failed / 4 warnings / 343.87 s**，`CI46_EXIT=0`；唯一 skip 仍 `test_auth_restart.py:18`；`test_run_queue.py` 未纳入（沿用“CI 纳入另卡”先例） | `output/qwen301/logs/ci46.txt` |
| 全量 `pytest tests/` | **2439 passed / 0 failed / 20 skipped / 21 warnings / 1434.35 s (0:23:54)**，`PYTEST_EXIT=0`，199 个测试文件 / **2459 项**（= 231b 基线 2424/0/20 + 本卡 15 项） | `output/qwen301/full-suite.txt`、`full-suite-exit.txt` |
| 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` + `git diff --check` → **RUFF_EXIT=0（All checks passed）；DIFFCHECK_EXIT=0** | `output/qwen301/logs/ruff.txt` |
| 全量首跑（如实登记） | **1 failed（`test_demo_journey` 墙钟预算 30.07 s > 30 s）/ 2438 passed / 20 skipped / 1691.52 s**；单跑复验两次：首次 35.5 s 仍超（冷缓存）、第二次 **5 passed / 30.27 s**；第二轮全量复跑（上表）全绿。判定为 30 s 预算贴边抖动，非产品回归（本卡不触 demo journey 路径）；日志未删 | `output/qwen301/full-suite-run1-journeyflake.txt`、`logs/journey-standalone.txt`、`logs/journey-standalone2.txt` |

### 31.4 开发中的两次真实排错（如实登记）

1. **`claim_next_run` 的 Python/SQL 时钟混用**：候选过滤在 Python 侧拿 ORM float 与 `db_now` 的 SQL 表达式比较 → `TypeError`；先误改成 `session.scalar(db_now(session))`（`ArgumentError: Executable SQL expected, got Cast`），最终以 `session.scalar(select(db_now(session)))` 一次取 DB 时钟定值修复。scratch 复现脚本 `output/qwen301/repro.py` 留档。
2. **SQLite 事件序号竞争（真问题）**：全文件跑序下 `test_cancel_running` 间歇 503，captured log 显示 `IntegrityError`——SQLite `FOR UPDATE` 不锁行，取消者与执行中 Worker 并发 `_next_event_sequence` 抢同一 `(run_id, sequence)`。以 `_safe_write_retrying`（仅对 IntegrityError 有界重试 3 次）收口，连续 3 轮全文件复跑稳定。另发现测试自造的 legacy 行缺 `request` 元数据会触发 `load_run` KeyError→503，属测试准备错误，已在测试内补齐真实形状。

### 31.5 边界与未做

- **at-least-once**：崩溃恢复=重领重跑，同一次请求可能被执行多次（模型侧预算由图内 `MAX_MODEL_CALLS` 等既有上限约束）；**不声称 exactly-once**。
- `MAX_ATTEMPTS=2`（执行尝试上限 2 次，第 3 次领取判失败）是**基线常量**，最终阈值待 Lead 裁定；`run_queue_attempts_exhausted` 是本卡新增的队列专属稳定码，未触碰任何既有错误码。
- 领取扫描按 `created_at` 排序、单轮最多看 `limit*3` 行，海量 legacy running/interrupted run 混入时可能需要翻页——基线实现按当前规模足够，未做游标分页。
- Worker 执行历史在领取时加载（`before=record.started_at`），与 `/stream` 的创建时加载语义一致；教师撤课等运行中授权变化由工具层的既有实时校验兜底。
- **未把 `test_run_queue.py` 加入 `ci.yml` 快清单**（沿用“CI 纳入另卡”先例）；未跑 GitHub `quality` 回执与 PG `enterprise-contract`（本卡零 PG 面改动；PG 侧 `FOR UPDATE` 行锁使序号重试按设计退化为不触发）。
- `expire_batch` 启动清扫与队列重领并存：queue 来源的 expired run 被扫成 `interrupted` 后仍是队列候选，不丢任务。
- 未动 QWEN-311；完成 301 即停，hold 等验收。
- 证据等级：**offline**。

## 32. QWEN-301b 队列测试纳入 CI 快清单（2026-10-25，分支 `qwen/wave3-queue`，零模型调用、产品与测试逻辑零改动）

Lead §4（`[2026-10-25 00:38]`）派工逐字：「把 `tests/a/test_run_queue.py` 加入 `ci.yml` 快清单 46→47，预期 **568/1**；更新 README/矩阵；只改 CI/文档；完成后 `[DONE]`。」

### 32.1 改动（1 个 CI 文件 + 3 个文档文件）

| 文件 | 改动 | 锚点 |
|---|---|---|
| `.github/workflows/ci.yml` | `quality` job portable 快清单 **46 → 47 个文件**：在 `tests/a/test_observation_claim_support.py` 后加 `tests/a/test_run_queue.py`（新行 `:219`，旗标行 `--no-cov --benchmark-disable -q` 顺延 `:220`）；`enterprise-contract` 仍 **38**、MCP 协议独立步骤仍在 | `:219` |
| `README.md` | `:58` CI 行换成本卡 47 文件 **568/1** 记录，301 的 553/1 降为同格「再前」 | `:58` |
| `docs/TEST_MATRIX.md` | 文件矩阵 `test_run_queue.py` 行补 `F` 标记并更新备注；新增 §29（追加） | `:126`、§29 |
| `docs/CLAIMS_LEDGER.md` | §31.5「未把队列测试加入快清单」条目由本卡关闭；新增本节 §32（追加） | — |

**未改**：任何 `backend/`、`tests/`、`scripts/` 文件；`PROMPT_VERSION`、产品逻辑、测试逻辑一字未动。

### 32.2 实测（offline，零计费模型调用）

| 量 | 值 | 证据 |
|---|---|---|
| 清单机械重取 | `yaml.safe_load` 读 `ci.yml`：portable **47** 条、无重复、0 缺失、末位即本卡文件 | `output/qwen301b/logs/portable-list.txt` |
| 前置 `init_db()` | exit 0（全新 `output/qwen301b/ci.db`） | — |
| **CI 同形子集（47 文件）** | **568 passed / 1 skipped / 0 failed / 4 warnings / 307.08 s (0:05:07)**，`CI47_EXIT=0`；= 301 记录的 553/1 + 该文件既有 **15** 项，与 Lead 预计 **568/1** 逐数一致；唯一 skip 仍是 `test_auth_restart.py:18` | `output/qwen301b/logs/ci47.txt`、`ci47-exit.txt` |
| 门 | `git diff --check` | exit 0（仅 CRLF 归一化 warning） |
| 全量 | **未重跑**：本卡 0 新增用例项、产品零改动，记录数仍为 301 的 **2439/0/20 / 2459 项** | §31.3 |

### 32.3 边界与未做

- 本卡只改 CI/文档，零模型调用、未读 `.env`、未装依赖、未跑探针（不主张 `attempts=0` 探针值）。
- **未跑 GitHub `quality` 真实回执**（remote 证据，由 Lead 判读）；全量与 PG 面未重跑（本卡零产品/零用例项改动，记录数不变）。
- 随后开工 QWEN-311（`qwen/wave3-prompt`）。
- 证据等级：**offline**。
