# PostgreSQL 检查点跨进程恢复验收

2026-10-13：本机 Docker 的 `pgvector/pgvector:pg16` 隔离数据库（PostgreSQL 16.15），7 项通过（30.00 秒）。运行使用 Python 3.10、真实 LangGraph 与 PostgreSQL Checkpointer，模型与检索仍为测试桩。没有加载 `.env` / `.env.enterprise`，没有云端调用费用。

## 实际覆盖

- 普通问答：生成并进入人审，保存检查点后进程直接 `os._exit(73)`，新进程通过审核。
- 学习包：未使用证据、Reviewer 一次返工改变来源两种场景，各覆盖通过、替换答案、拒绝，共 6 项。
- 新进程恢复的 checkpoint ID 与退出前一致；恢复前待执行节点是 `approval`，恢复后没有待执行节点。
- 恢复阶段的模型及检索方法直接抛错，证明这条审核恢复路径没有重新生成内容；预算和返工计数保持一致。
- 通过审核保留学习包及分项引用，最终引用仍是实际使用来源的并集；替换文本清除旧学习包和引用；拒绝时清除交付证据与引用。
- 使用生产代码 `initialize_checkpointer` / `shutdown_checkpointer`。每例使用 UUID thread_id，结束时仅删除自己的检查点并确认删除成功。

测试文件：`tests/a/test_learning_checkpoint_postgres.py`；独立进程探针：`tests/helpers/checkpoint_restart_worker.py`。原 CI enterprise-contract 作业已包含此测试文件，现在会执行全部 7 项；没有远端 CI 执行结果。

## 复核命令

使用已安装的项目依赖。下面的数据库账号和密码只适用于一次性本机测试；不得换成业务数据库。容器数据位于 tmpfs，不挂载已有数据卷。

```powershell
# 项目根目录；需已存在 pgvector/pgvector:pg16 镜像。
$checkpointContainerId = docker run --detach --pull never --publish 127.0.0.1:55439:5432 --env POSTGRES_USER=checkpoint_test --env POSTGRES_PASSWORD=disposable-test-only --env POSTGRES_DB=checkpoint_test --tmpfs /var/lib/postgresql/data:rw pgvector/pgvector:pg16
if ($LASTEXITCODE -ne 0) { throw '测试容器创建失败，请检查端口占用' }
docker exec $checkpointContainerId pg_isready -U checkpoint_test -d checkpoint_test
# 确认 accepting connections 后，在同一 PowerShell 中执行：
$env:TEST_V2_POSTGRES_URL = 'postgresql://checkpoint_test:disposable-test-only@127.0.0.1:55439/checkpoint_test?connect_timeout=5'
$env:A3_OFFLINE_DEMO = '1'
python -m pytest tests/a/test_learning_checkpoint_postgres.py --no-cov --benchmark-disable -q --junitxml=output/checkpoint-restart/pytest.xml
# 只删除上面新创建的测试容器，不操作业务容器。
docker rm --force $checkpointContainerId
Remove-Item Env:TEST_V2_POSTGRES_URL
```

本机使用 `D:/Anaconda3/envs/dxtorch/python.exe`，`PYTHONPATH=D:/xunfei/triple-U/.tmp/p0-deps;D:/xunfei/triple-U`。Windows 探针使用 Selector 事件循环兼容 psycopg。首次沙箱执行因本机异步连接阻塞超时，经授权在沙箱外重跑后 7 项通过。未设置 `TEST_V2_POSTGRES_URL` 时 7 项跳过，跳过不算验收通过。

本次通过报告为 `output/checkpoint-restart-20261013/pytest-unrestricted.xml`；首次超时报告保留供排查。测试后查询确认 `checkpoints`、`checkpoint_writes`、`checkpoint_blobs` 均为 0 行，一次性容器已删除。报告和临时数据库不提交仓库。

## 验收边界

这证明的是**应用进程在检查点已提交后退出，新进程从人审节点恢复**。数据库服务在测试期间持续运行；没有验证数据库崩溃、磁盘故障、任意节点中途退出、业务写操作的 exactly-once、租约抢占或自动恢复。

测试直接调用 Graph，不覆盖 HTTP 登录、教师课程关系、Run 审计表与检查点的一致性、前端 SSE 重连；这些仍需完整企业环境验收。模型和检索为桩，因此不产生新版 76 条问答集或 24 条学习包集的云端质量指标。

后续批次已另外补充 [5 项真实 PostgreSQL API 故障修复](RUN_RECONCILIATION.md) 和 [真实登录跨进程及课程授权验证](AUTH_AND_COURSE_ACCESS.md)。本页 7 项历史结果的范围不因此扩大。仍需数据库服务故障、真实身份与完整 Agent 流程联合验收，以及经用户授权的云端运行和人工质量评审；真实模型与 Embedding 调用会产生费用。
