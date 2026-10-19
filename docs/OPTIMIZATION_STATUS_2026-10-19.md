# 优化状态（2026-10-19）· Wave 0 基线与治理

> 执行：Qwen（唯一主执行者）· 分支：`qwen/wave0-baseline`（基于 `main@23766d9`）· 依据：[Qwen 优化主计划](QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md) §6 Wave 0 / §9 第一周清单。
> 本文件只写**本轮实测/已核对**结果；历史归档见 [OPTIMIZATION_STATUS_2026-10-18.md](OPTIMIZATION_STATUS_2026-10-18.md)。本轮未修改任何业务代码与测试断言。

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
| 全量 `pytest tests/`（189 文件） | **2234 passed / 2 failed / 19 skipped**（650.31 s） | offline |

两个失败的定位（详见 `output/qwen-baseline-2026-10-19/report.md`，本地不外发）：

1. `test_celery_worker_process.py::test_duplicate_delivery_and_expired_lease_recovery` —— Windows kombu `filesystem://` broker 需要 pywin32，本环境缺 `pywintypes`；Linux CI/nightly 不受影响。**未改代码**；待决策：装 pywin32 或依赖 Linux nightly 覆盖。
2. `tests/integration/test_artifacts_api.py::TestGenerateTTS::test_short_text_returns_audio_path` —— 服务在无讯飞凭据时合法回退 `edge-tts`（200 + 音频路径），测试允许值只有 `(xunfei, mock, cache)`；测试期望过期，非产品回归。Wave 1 修 1 行断言。

**未复跑（如实记录）**：PG/Redis 企业合同组合（历史 353 passed，QWEN-105）、远端 CI run #17/#18/#19 状态（本机无 gh CLI）、nightly 远端运行记录、Linux 锁安装冒烟、gitleaks/pip-audit。本轮付费模型调用 **0 次**（用量 0/0，费用 0）。

## 二、QWEN-001 声明台账

产出 [docs/CLAIMS_LEDGER.md](CLAIMS_LEDGER.md)：README/evals/十模块文档/竞赛材料/状态归档/许可清单/主计划自身共 **50+ 条对外数字与"已实现"措辞**逐条标注状态（有证据 / 有证据-历史 / 需复跑 / 措辞需修正 / 愿景 / 待人工）与证据等级。关键发现：

- README 数字全部与已发表脱敏汇总/归档记录一致，且多数自带"历史"限定（R7–R13）；需要小改的是"在线契约"措辞（R9/R13）与"企业级"边界句（R17）。
- `V2_TEN_MODULE_IMPLEMENTATION.md` 的 `PROMPT_VERSION=v2.4` 与代码 v2.8 脱节（T1）；`evals/README.md`"76 条未完成真实云端验收"过期（E1）——修正动作归 Wave 1 QWEN-103。
- 竞赛材料硬数字过期：`12 Agent`（实测 16 个 BaseAgent 子类）、`90 路由`（实测 187 个路由装饰器）、"6 种产物"（实测目录 ≥7 类）（D1–D3）。
- 诚实性正例保持不动：72 次运行不宣称质量优势、费用 unknown 不写 0、"depends_on 未执行"主动降级表述。
- **本轮未修改任何被核对文档正文**（避免与 Wave 1 QWEN-103 的"文档修正+CI 验证"流程重复）。

## 三、QWEN-002 测试分层矩阵

产出 [docs/TEST_MATRIX.md](TEST_MATRIX.md)：189 个 Python 测试文件逐一映射 fast（CI quality 37）/ contract-pg（enterprise 37 + MCP 1）/ nightly（全量收集）/ manual；另记 34 个前端 `.mjs` 单元与 1 个桌面测试**当前不在任何 CI**。缺口与 nightly 计划 6 项（sandbox 安全 P0 独立步骤、前端单元进 fast、`test_v2_retrieval_postgres` 疑似漏配、tests/b+integration 报表、扩展覆盖率门禁、nightly 远端首跑核验）。

## 四、分支与提交

- `qwen/wave0-baseline` 自 `main@23766d9` 建立；本轮提交仅含上述三份文档（新增 docs 文件），无代码/测试/工作流变更。
- 提交前自检：`git status --short` 无未预期文件；`git diff --check` 干净；未提交 `output/` 任何内容；无密钥/私有数据。

## 五、下一步（Wave 0 出口 → Wave 1）

1. 远端复核 CI run 状态（#19 及后续），把 run 编号/结论写入状态文档。
2. 手动触发一次 nightly，记录耗时与 skip 清单（矩阵 §5.1）。
3. QWEN-003（依赖/许可/SBOM 基线）按用户本周范围指示**未排入**；如需要可随后补。
4. Wave 1：QWEN-101 人工盲评工具包（不代填评分）；QWEN-102 需用户付费授权与新任务题集——**未经授权不调用模型**。
5. 台账"措辞需修正"条目按 QWEN-103 执行，README 更新用最新复跑数字并注明环境。
