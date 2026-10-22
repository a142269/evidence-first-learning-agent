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
| R4 | L27 | V2 旗舰链路（受限规划→Tutor→Practice→Reviewer→一次返工→按需人审） | 有证据 | offline（契约）+ cloud（单次采集） | 代码 `learning_package.py`（v2.8）+ 便携套件今日 369 passed；真实后端 13 条标准场景采集通过（cloud 历史）。契约测试不等于内容质量。 | 保持 |
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
