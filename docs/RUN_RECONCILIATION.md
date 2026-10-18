# 从检查点修复失败运行

当 Graph 已保存待审或最终检查点，但 Run 结果写库失败时，任务会显示 `failed`。新增接口允许授权教师从已提交的检查点修复该任务，保留既有模型结果与引用。

## 调用与行为

```http
POST /api/v2/learning-runs/{run_id}/reconcile
Authorization: Bearer <教师登录令牌>
```

不需要请求体。返回 JSON，结构与 `GET /api/v2/learning-runs/{run_id}` 相同，不是 SSE。学习包页面已有教师专用“检查并恢复已保存结果”按钮；恢复到 `awaiting_approval` 后仍需审核，教师可填写替换答案后交付或拒绝。

| 条件 | 行为 |
| --- | --- |
| Run 为 `failed` / `interrupted`，检查点停在有效的人审中断 | 修复为 `awaiting_approval`；学生仍看不到草稿和引用 |
| Run 为 `failed` / `interrupted`，检查点已正常结束 | 修复为 `completed` 或 `rejected`；沿用已保存的审核决定 |
| Run 为 `failed` / `interrupted`，检查点已正常结束且只交付了已审核部分 | 修复为 `partially_completed`；沿用 `partial_completion`，未交付内容不会恢复，也不会被升级为 `completed` |
| Run 为 `running` / `reviewing` 且租约已过期 | 原子标记 interrupted，再检查稳定检查点，不重新执行节点 |
| Run 为 `running` / `reviewing` 且租约有效，或其他不可修复状态 | 409 `run_not_reconcilable`，不抢占执行权 |
| 检查点缺失、节点报错、仍有非审核节点待执行 | 409 `checkpoint_not_settled`，不重放任务 |
| Run、用户、课程、问题或审核要求与检查点不匹配 | 409 `checkpoint_identity_mismatch` |
| 旧工作流版本或旧共享 thread_id | 409 `legacy_run_restart_required` |
| 读取检查点期间 Run 状态被其他请求修改 | 409 `run_state_changed`，不覆盖新状态 |
| Checkpointer 未启用 / 读取失败 / 业务库失败 | 503，返回稳定错误码，不返回连接串和异常正文 |

身份与课程权限复用现有授权逻辑，仅 teacher/admin 可操作。普通学生即使拥有该任务也不能修复。生产模式按账号查询课程授权；开发模式可保留环境变量白名单，见 [登录与课程授权](AUTH_AND_COURSE_ACCESS.md)。

修复只读取检查点，不执行 Graph 节点，不再次调用模型、检索或工具。学习包通过审核时保留分项引用；人工替换学习包答案时清除旧结构化内容与引用；拒绝时不交付待审内容。要求人审的任务不会因为修复绕过审核。部分成功任务沿用 `partial_completion`，只恢复已审核并已交付的内容；未交付的练习或题目文本不保留在稳定状态中，也不会被补造。修复后的 `partially_completed` 只表示“已交付部分经过审核”，不表示未交付内容已被验证，也不等于完整 `completed`。

Run 状态更新使用带原状态条件的 SQL 更新，和 `run.reconciled` 审计记录在同一事务提交；并发请求只有一次能够成功。查询事件接口可看到修复事件，但仍按既有白名单过滤事件数据。修复期间不重新写入检索日志，原检索日志若已丢失，不会据此补造。

## 验证

2026-10-13 定向回归 **112 passed**：修复故障注入 31 项、已有生命周期 19 项、学习包 27 项、离线采集器 35 项。覆盖最终/待审结果写入失败、审核后结果写入失败、并发修复、审计写入失败回滚、缺失/旧版本/错误归属检查点、学生草稿隔离和学习包引用。

另修复客户端断连时的顺序：先取消并等待 Graph 任务结束，再保存 `interrupted`，避免在 Graph 仍执行时把任务开放为可修复状态。

```powershell
python -m pytest tests/a/test_learning_run_reconciliation.py tests/a/test_learning_runs_v2_lifecycle.py tests/a/test_learning_package.py tests/a/test_learning_package_collection.py --no-cov --benchmark-disable -q
python -m ruff check backend/app/agent_runtime/learning_graph.py backend/app/agent_runtime/run_audit.py backend/app/api/v2/run_lifecycle.py backend/app/api/v2/learning_runs.py tests/a/test_learning_run_reconciliation.py --select F,E9
```

本机 Python 和离线依赖路径见实施记录；结果位于 `output/reconcile-20261013/pytest-final.xml`，不提交。测试使用 SQLite、内存 Checkpointer 与模拟模型，Ruff F/E9 通过。CI 已加入新测试，未执行远端 CI。本批无前端改动，没有重新构建。

2026-10-18 新增 `partially_completed` 交付链路的修复回归：结果写入失败后由教师修复为部分完成、部分结果不能升级为完整完成、待审部分结果仍保持草稿隔离、未交付题目文本不进入持久化状态。测试位于 `tests/a/test_learning_package_partial.py`，本地结果与运行命令见 [优化状态（2026-10-18）](OPTIMIZATION_STATUS_2026-10-18.md)。

## 执行租约与真实 PostgreSQL 验证（2026-10-13/14）

- 每次创建或领取审核时生成独立 execution_id；租约使用数据库时钟，有效期 45 秒，执行期间每 10 秒续期。失去租约后停止 Graph，并拒绝该执行代次写入 Run 结果、节点审计和检索日志。
- 启动时最多清理 1000 条已过期任务；其余可由显式 reconcile 识别。不会自动重新执行模型或抢占有效任务。旧无租约任务不会被自动标记为过期。
- 检查点携带 execution_id；如果新审核已领取但仅保存了上一执行代次的检查点，身份不匹配时拒绝修复，防止复活旧决定。
- 11 项租约单测、2 项 SQLite 迁移保留数据测试通过；与原修复/生命周期/学习包/采集器的 112 项相关测试兼容。
- 新增 5 项真实 PostgreSQL + ASGI API 故障注入：待审、无需审核的最终结果、审核通过、人工修改、拒绝。进程在检查点提交后、Run 结果保存前直接退出；新进程模拟租约到期并通过接口修复，验证过期与修复审计各写入一次、旧执行代次不能覆盖结果。
- 5 项通过报告为 `output/lease-recovery-20261013/postgres-api-verified.xml`（39.27 秒）。身份、模型与检索仍是桩；后续真实登录的独立进程测试见身份说明，不能混称为同一次端到端测试。
- 前端模拟 API 验证了失败查询、恢复到待审、教师替换交付、停止本次请求和窄屏布局；停止请求后需查询服务器状态，不将浏览器取消直接当作服务器已停止的证明。

```powershell
python -m pytest tests/a/test_run_leases.py tests/a/test_run_lease_migration.py tests/a/test_postgres_api_recovery.py --no-cov --benchmark-disable -q
```

PostgreSQL 测试必须配置一次性 `TEST_V2_POSTGRES_URL`，探针会执行迁移往返，禁止指向业务库。新版本部署前执行 `alembic upgrade head`，不能依赖 create_all 为旧表新增租约列；迁移 `20261013_0007` 同时补齐纯 Alembic 新库此前缺失的 agent_runs 表。

## 尚未覆盖

- 任意未完成节点的继续执行尚未实现；只有待审或已经结束的稳定检查点可修复。原调用在外部服务中是否实际停止，也不由租约保证。
- Run 与 Graph 检查点不在一个原子事务中。这是已稳定检查点的人工触发修复，不是数据库跨表/跨连接强一致保证。
- 数据库服务崩溃、Run 和 Checkpointer 的跨连接原子一致性、真实身份与模型共同参与的完整恢复场景及云端质量仍待验收。租约只约束 Run 写入，不保证 Checkpointer 写入的 exactly-once。
- `latency_ms` 仍按开始到结果保存的总历时计算，包含审核等待和故障停留时间，不能当作模型执行耗时。

本次没有云端调用。真实模型和 Embedding 验收需事先授权，并会产生费用。
