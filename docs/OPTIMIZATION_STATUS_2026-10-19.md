# 优化状态（2026-10-19）· Wave 0 基线与治理

> 执行：Qwen（唯一主执行者）· 分支：`qwen/wave0-baseline`（基于 `main@23766d9`）· 依据：[Qwen 优化主计划](QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md) §6 Wave 0 / §9 第一周清单。
> 本文件只写**本轮实测/已核对**结果；历史归档见 [OPTIMIZATION_STATUS_2026-10-18.md](OPTIMIZATION_STATUS_2026-10-18.md)。§一–§三为 Wave 0 首轮交付，当时未修改任何业务代码与测试断言；§六为 Lead 批准的收口补丁（QWEN-004 / QWEN-120），仅改测试期望、测试 skip 与 CI 清单，未改产品行为。

## 一、QWEN-000 基线复跑（本机 Windows，conda `evidence-agent-py312`，Python 3.12.15）

| 检查 | 结果 | 证据等级 |
|---|---|---|
| Ruff（CI 规则 F821,F823,E9，backend+scripts+tests） | 通过 | offline |
| Mypy strict（CI 精选 16 模块；需 `PYTHONUTF8=1`，Windows GBK locale 问题） | 通过（16 files no issues） | offline |
| Alembic `upgrade head → downgrade base`（独立 SQLite） | 通过（exit 0/0） | offline |
| CI 便携 V2 契约套件（`ci.yml` quality 全清单 37 文件） | **369 passed / 1 skipped / 0 failed**（58.54 s）；skip=`test_auth_restart`（需显式一次性 PG，CI 同） | offline |
| 覆盖率门禁（5 文件） | **110 passed**；learning_package 94% / claim_support 83% / 合计 92.44%（≥80） | offline |
| 前端 `npm run build`（vue-tsc + vite，node v24.13.0，本机既有依赖，未联网下载） | 通过（首败为沙箱拒绝 esbuild 清理临时文件；`TEMP` 重定向后通过，非产品缺陷） | offline |
| Compose `config` 解析（demo / +enterprise / production，占位值副本后即删） | 三套全部 exit 0 | offline |
| 全量 `pytest tests/`（189 文件） | 首轮 **2234 passed / 2 failed / 19 skipped**（650.31 s）；收口后复跑 **2235 passed / 0 failed / 20 skipped**（612.61 s），见 §六 | offline |

首轮两个失败的定位（详见 `output/qwen-baseline-2026-10-19/report.md`，本地不外发；收口方式见 §六）：

1. `test_celery_worker_process.py::test_duplicate_delivery_and_expired_lease_recovery` —— Windows kombu `filesystem://` broker 需要 pywin32，本环境缺 `pywintypes`；Linux CI/nightly 不受影响。首轮**未改代码**，收口时按 Lead 决定改为条件 skip（不装 pywin32）。
2. `tests/integration/test_artifacts_api.py::TestGenerateTTS::test_short_text_returns_audio_path` —— 服务在无讯飞凭据时合法回退 `edge-tts`（200 + 音频路径），测试允许值只有 `(xunfei, mock, cache)`；测试期望过期，非产品回归。收口时补 `edge-tts` 允许值。

**未复跑（如实记录）**：PG/Redis 企业合同组合（历史 353 passed，QWEN-105）、远端 CI run #17/#18/#19 状态（本机无 gh CLI）、nightly 远端运行记录、Linux 锁安装冒烟、gitleaks/pip-audit。本轮付费模型调用 **0 次**（用量 0/0，费用 0）。

## 二、QWEN-001 声明台账

产出 [docs/CLAIMS_LEDGER.md](CLAIMS_LEDGER.md)：README/evals/十模块文档/竞赛材料/状态归档/许可清单/主计划自身共 **50+ 条对外数字与"已实现"措辞**逐条标注状态（有证据 / 有证据-历史 / 需复跑 / 措辞需修正 / 愿景 / 待人工）与证据等级。关键发现：

- README 数字全部与已发表脱敏汇总/归档记录一致，且多数自带"历史"限定（R7–R13）；需要小改的是"在线契约"措辞（R9/R13）与"企业级"边界句（R17）。
- `V2_TEN_MODULE_IMPLEMENTATION.md` 的 `PROMPT_VERSION=v2.4` 与代码 v2.8 脱节（T1）；`evals/README.md`"76 条未完成真实云端验收"过期（E1）——修正动作归 Wave 1 QWEN-103。
- 竞赛材料硬数字过期：`12 Agent`（实测 16 个 BaseAgent 子类）、`90 路由`（实测 187 个路由装饰器）、"6 种产物"（实测目录 ≥7 类）（D1–D3）。
- 诚实性正例保持不动：72 次运行不宣称质量优势、费用 unknown 不写 0、"depends_on 未执行"主动降级表述。
- **本轮未修改任何被核对文档正文**（避免与 Wave 1 QWEN-103 的"文档修正+CI 验证"流程重复）。

## 三、QWEN-002 测试分层矩阵

产出 [docs/TEST_MATRIX.md](TEST_MATRIX.md)：189 个 Python 测试文件逐一映射 fast（CI quality 37）/ contract-pg（enterprise 首轮统计 37 + MCP 1，收口后 **38**）/ nightly（全量收集）/ manual；另记 34 个前端 `.mjs` 单元与 1 个桌面测试**当前不在任何 CI**。缺口与 nightly 计划 6 项（sandbox 安全 P0 独立步骤、前端单元进 fast、`test_v2_retrieval_postgres` 疑似漏配、tests/b+integration 报表、扩展覆盖率门禁、nightly 远端首跑核验）——其中第 3、4 项已在本轮 §六 分别转为"阻塞待决策"与"已修复"。

## 四、分支与提交

- `qwen/wave0-baseline` 自 `main@23766d9` 建立；本轮提交仅含上述三份文档（新增 docs 文件），无代码/测试/工作流变更。
- 提交前自检：`git status --short` 无未预期文件；`git diff --check` 干净；未提交 `output/` 任何内容；无密钥/私有数据。

## 五、下一步（Wave 0 出口 → Wave 1）

1. 远端复核 CI run 状态（#19 及后续），把 run 编号/结论写入状态文档。
2. 手动触发一次 nightly，记录耗时与 skip 清单（矩阵 §5.1）。
3. QWEN-003（依赖/许可/SBOM 基线）按用户本周范围指示**未排入**；如需要可随后补。
4. Wave 1：QWEN-101 人工盲评工具包（不代填评分）；QWEN-102 需用户付费授权与新任务题集——**未经授权不调用模型**。
5. 台账"措辞需修正"条目按 QWEN-103 执行，README 更新用最新复跑数字并注明环境。

## 六、Wave 0 收口补丁（QWEN-004 + QWEN-120，2026-10-19 追加）

### QWEN-004 两处失败收口（仅改测试，不改产品行为）

| 项 | 改动 | 实测 | 证据等级 |
|---|---|---|---|
| TTS 期望过期 | `tests/integration/test_artifacts_api.py::TestGenerateTTS::test_short_text_returns_audio_path` 允许值改为 `(xunfei, edge-tts, mock, cache)`；`edge-tts` 是 `services/multimodal/tts_xunfei.py` Level 2.5 的合法降级返回值 | 定向复跑 2 文件 **24 passed / 1 skipped / 0 failed**（58.37 s） | offline |
| Windows Celery 依赖 | `tests/a/test_celery_worker_process.py` 增加模块级 `pytestmark` skipif：`sys.platform == "win32"` 且 `importlib.util.find_spec("pywintypes") is None`，原因写明"kombu filesystem broker 需要 pywin32；Linux nightly 全量套件继续覆盖本契约" | 本机 skip 生效（`-rs` 打印原因）；未安装 pywin32，未改共享环境 | offline |
| 全量复跑 | 同一命令、新 `--basetemp`、独立 SQLite（`close-full.db`，`init_db` 初始化） | **2235 passed / 0 failed / 20 skipped**（612.61 s）。较首轮 +1 passed（TTS 修复）、+1 skipped（Celery 由 failed 变条件 skip），总数 2255 不变 | offline |
| 静态检查 | `ruff check tests/ --select F821,F823,E9` 与改动的两个文件 `F,E9` | 全部通过 | offline |

如实记录的一次假失败：定向复跑第一次把 `DATABASE_URL` 指向未初始化的一次性 SQLite，`tests/integration/test_artifacts_api.py::TestMetrics::test_summary_endpoint` 报 `no such table: agent_runs`；对该库执行 `init_db()` 后同一组 **24 passed**，属我的环境准备遗漏，非产品回归，首轮全量运行不受影响。

另注：全量复跑启动时 `test_celery_worker_process.py` 的 skip 原因文案尚未加"本文件不在 fast/enterprise 清单、由 Linux nightly 覆盖"这句限定，日志里的文案与最终提交略有出入；收口后又单独复跑该文件确认 **1 skipped**、原因文案与提交一致，`ruff F,E9` 通过。

### QWEN-120 CI 快速收口

| 项 | 结论 | 证据等级 |
|---|---|---|
| `tests/a/test_v2_retrieval_postgres.py` 确实漏配 | 已加入 `.github/workflows/ci.yml` enterprise-contract 的 pytest 清单（37 → **38 文件**）；本机用一次性 pgvector 容器（tmpfs、仅绑 `127.0.0.1:55432`、跑完即 `docker stop --rm` 删除）实测 **1 passed**（1.56 s，Alembic `upgrade head` + 1024 维向量 + 无付费 Embedding 桩） | pg |
| 前端 `.mjs` 单元进 fast | **QWEN-120 首测阻塞，已按 Lead 裁决转 QWEN-121 完成**：本机首测 **17 passed / 21 failed**（34 文件、38 个顶层结果，node v24.13.0），失败源于仓库缺失的 `frontend/integrated-map-src/`、缺失的 `src/views/CockpitView.vue` 与过期断言；当时未装 `|| true`、未做"只跑绿文件"的白名单。处置见下一小节。 | offline |
| 工作流校验 | `yaml.safe_load` 解析 `ci.yml` 通过，enterprise 清单计数与新增文件名核对一致 | offline |

收口后提交：`e74151f`（测试 + CI）、本轮文档与台账更新；未合并 `main`（等 Lead 确认）。

### QWEN-121 前端测试方案 A（Lead 2026-10-19 [DECISION] 批准，含硬约束）

| 步骤 | 实测 | 证据等级 |
|---|---|---|
| 孤儿测试隔离（只移不删） | `git mv` **17 个**（不是先前汇报的 16 个）依赖未提交源码的用例到 `frontend/tests/_orphaned/`，新增 `_orphaned/README.md` 逐文件列出缺失路径与恢复办法 | offline |
| 计数更正 | 先前 [BLOCKER] 按"每个文件的第一条报错"分类，低估了 1 个：`demoLearnerName.test.mjs` 同时读取 4 个 `integrated-map-src/**` 文件，且它对 `src/constants/companion.ts` 的 `不出现"演示学习者"` 断言与当前实现冲突（该文件把 `演示学习者`/`张三` 一起放进 `GENERIC_LEARNER_NAMES` 占位名集合）。故孤儿集合为 16（含 `integrated-map-src`）+ 1（`routerRoutes` 读缺失的 `CockpitView.vue`）= 17 | offline |
| 过期断言修正 | 4 个文件按当前源码改写并加"当前源码依据"注释：`mistakesCourseSwitching`（课程选项现由 `@/api/knowledge` 的 `listCourses` 动态注入，MistakesView.vue:66-90，源码不再有硬编码 "Python"）、`resourcesRealDataChinese`（`course: requestedCourse` 快照 + "无课程标记则可见"的过滤新语义，ResourcesView.vue:1273/1279/616-619/658-663）、`dashboardChineseTimeline`（旧 `wp.kp_id` 薄弱点列表在本仓库不存在，AI 洞察现为三张焦点卡，改断言 `localizeKnowledgePointLabel(activeMistakeFocus.kp_id)`，DashboardView.vue:1466）、`homeOrbitCentering`（轨道图已从 HomeView 迁到 LoginView，`scale(0.53)` 样式全仓不存在，改为"首页不含 OrbitDiagram + 登录页挂载 + 无 translateX(36px) 补偿"） | offline |
| 产品 bug 判定 | 未发现需按 Lead 约束 2 停下来上报的产品缺陷：4 处都是"测试指向旧版 UI/旧实现"，当前源码有内建注释说明其设计意图（如历史无课程标记资源仍可见、快照防竞态）。**但** `dashboardChineseTimeline`/`homeOrbitCentering` 的语义被弱化改写，若 Lead 认为那两个 UI 属应恢复的产品功能，应回退这两处并转为产品任务 | offline（判读性结论，非验收） |
| 本地验证 | `node --test tests/*.test.mjs`（cwd=frontend，node v24.13.0）：17 文件、21 个顶层结果、**0 failed**、exit 0（430.9 ms）；`_orphaned/` 17 文件不被 glob 命中 | offline |
| CI 接入 | `.github/workflows/ci.yml` frontend job 新增 step `Frontend unit tests (node:test)` → `node --test tests/*.test.mjs`，**不加** `|| true`；`yaml.safe_load` 解析通过 | offline |

### 台账/矩阵一致性

- `docs/CLAIMS_LEDGER.md` R11 更新为收口后的全量数字；S8 改写为"已隔离 + 措辞仍待修正"的当前事实；新增 S9（`THIRD_PARTY_NOTICES.md` L453 的 59 个暂存文件说法已过期，实测该路径 `git ls-files` = 0，仅剩 14 个空目录）。
- `docs/TEST_MATRIX.md` §6 追加 QWEN-121 收口行，§5.3 由"阻塞"改为"已接（方案 A）"，§3 前端表行改为 17 运行 + 17 孤儿。
- 主计划 QWEN-343 / QWEN-401 各加一条跟踪项（孤儿测试处置与 `integrated-map-src` 来源结论），按 Lead 约束 5 执行。
