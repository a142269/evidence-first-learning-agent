# V2 本地提交范围（2026-10-15）

当前分支 `feat/enterprise-agent-rag-stack`。工作树中的 V2 实现、V1 生产权限收口、迁移、前端、评测与测试可作为一个待审提交候选；本文件只记录范围，不暂存或提交。正式提交前仍需逐文件复核差异并运行密钥扫描。

## 候选范围

- `backend/app/`：V2 学习运行时、持久会话/课程授权、摄取与检索、费用护栏，以及 V1 生产路由白名单和已核验的学生资源权限。
- `alembic/versions/20261013_0007_run_execution_leases.py` 与 `20261014_0008` 至 `0011` 五个迁移文件。
- `frontend/src/` 与 `frontend/tests/learningStream.test.mjs`：学习包、SSE、登录同源 API。
- `scripts/` 中当前已修改或新增的 V2 回填、重建、评测、权限管理与离线检查脚本；`evals/` 中新版固定用例、阈值和说明。
- `tests/a/` 中当前已修改或新增的权限、运行、检索、摄取、评测测试及 `tests/helpers/`；`.github/workflows/ci.yml`、`docker-compose.enterprise.yml`、`requirements-mcp.txt`、`README.md` 和本轮 V2/部署文档。

此范围是路径候选，不表示这些目录以后新增的任意文件可自动进入提交。`docs/JOB_SEARCH_PACKAGE.md` 属于求职文案，建议与运行时代码分开审核。

## 明确排除

不要暂存 `.env*`（包括示例环境文件）、`data/rag/knowledge_index.json`、`reports/`、`output/`、`.playwright-cli/`、`cloud-embedding-smoke.md`、`control/` 及各类 pytest 临时目录。当前 `knowledge_index.json` 是大量本地生成差异；不用于 V2 pgvector 评测结论。不要对脏工作树执行全量 `git add .`、清理或重置。

## 已做的本地门槛

- V1 生产白名单、部署策略与 V2 授权：44 passed。
- V1 资源所有权、教师协作/资源组合：73 passed。
- `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` 和 `git diff --check`：通过。
- 新增的学习包 Planner 格式重试、连续失败后续跑、采集器持久化比较及 Embedding 检索组合：最终定向 **72 项通过**。前端 SSE 解析 5 项、演示资产检查 14 项通过。离线负载烟测 8 个端点各 30 请求均成功，但 cockpit p95 约 112.7 秒。
- Docker 启动后补充了学习包课程检索独立超时、结构化产物最多一次重试、服务商 JSON 输出模式和固定两步 Planner 示例；相关定向回归最终 128 项通过，Ruff 关键规则通过。真实隔离后端的 13 条标准学习包场景契约 13/13 通过。新批次累计上限经用户授权提高到 200 元，最终费用计数器保守预留 188.38166 元，非供应商账单；本轮没有由 Codex 下载依赖。
- 本机完整 `pytest tests/` 在可写临时目录下收集 2161 项；执行到约 37% 时中止，已见旧数据断言失败（题库 KP 53 对测试写死的 24、知识图谱 52 对文档写死的 28、画像 archetype 断言）。因此不能把本地完整 CI 称为绿色。远端 CI 未触发。
- 先前隔离 PostgreSQL 迁移及 10 项定向回归、Redis/Worker 故障注入、MCP stdio 协议、前端构建及模拟浏览器交互的细节见开发交接文档；这些不能替代远端 CI 或云端内容质量验收。

生产兼容影响：`APP_ENV=production` 只保留 V1 登录/注册、当前账号/注销、已发布课程目录、资源类型和已核验的学生资源接口；旧教师管理、知识库上传及其他学生数据页面返回 403，直至逐路由补齐课程和账号授权。V2 API 不受该白名单限制。上线前应由使用这些旧页面的部署方核对迁移路径。

在线证据保存在被排除的 `output/v2-eval-20261015/`：完整 76 条首轮报告、逐例进度、两条超时用例复测报告。提交代码时应另行审查并明确选择这些报告是否需要去标识化后归档；不能把本地测试数据库、Redis 卷、密钥文件和浏览器缓存一并提交。

## 2026-10-16 本地回归更新

此前约 37% 中止的记录是历史状态。修正旧数据断言及测试辅助函数后，在新隔离 SQLite 上完整运行 `pytest tests/`：**2149 passed、18 skipped，575.38 秒**；Ruff 关键规则、`git diff --check`、CI YAML 解析和演示资产检查 **14/14** 通过。CI Pytest 步骤现使用独立数据库并先初始化表；远端 CI 尚未触发。SQLite TF-IDF 构建不再逐分块重复保存全局词频表；上传分块数按 RAG 实际扫描结果统计。测试运行生成的 `data/artifacts/`、`knowledge_base/pytest_course_*/` 和其他本地产物继续排除，审查时只选择意图提交的代码、迁移、测试与文档。

最终安装 `psycopg[binary]` 并增加在线采集器“完整 resume 不登录、不重复请求”测试后，再次以全新 SQLite 完整运行：**2153 passed、18 skipped、24 warnings，626.37 秒**。独立空白 PostgreSQL 的 15 项检查点、API 进程恢复、摄取幂等、检索版本隔离和未完成节点续跑测试全部通过。摄取 PostgreSQL 测试桩同步补上生产实现已使用的 `count_source_chunks()`；该修改只修复测试环境，没有绕过产品断言。前端生产构建、Ruff 关键规则和 `git diff --check` 通过。
