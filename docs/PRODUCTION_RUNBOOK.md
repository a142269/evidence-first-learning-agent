# 生产 Runbook（模板 + 本机演练记录）— QWEN-403（2026-10-25，分支 `qwen/wave4-release`）

> **边界声明（必读）**：本文是运维**模板与演练记录**。**公网/TLS/域名/备份恢复/真实容器部署
> 均未验证**——本机无 Docker daemon、无公网主机；本文不宣称任何"已上线/已验证"。
> 生产拓扑以 [docker-compose.production.yml](../docker-compose.production.yml) 为准
> （postgres/redis/phoenix/migrate/backend/worker/frontend，仅 frontend 发布端口且默认绑
> 127.0.0.1，全部 secret `${VAR:?}` 强制，`APP_ENV=production`）。

## 1. 部署前置（未验证清单的来源）

1. `cp .env.production.example .env.production` 并填齐全部 `${VAR:?}` 变量（含 `QUOTA_*`，324b 已默认启用配额）；
2. `docker compose --env-file .env.production -f docker-compose.production.yml config` 校验渲染（**未跑：本机无 Docker daemon**，compose 文件头部同声明）；
3. 迁移由 `migrate` 服务在 backend 之前自动执行（`alembic upgrade head`，`service_completed_successfully` 门）；
4. 首个教师账号：`docker compose ... exec backend python -m scripts.manage_access create-teacher <account>` + `grant <account> --course <course>`（compose 头部注释口径，未演练）；
5. TLS 反向代理在 frontend 发布端口之前（见 §3）。

## 2. 健康检查与启动验证

| 检查 | 命令 | 预期 |
|---|---|---|
| 容器状态 | `docker compose --env-file .env.production -f docker-compose.production.yml ps` | 全部 healthy/Up；`migrate` 为 exited(0) |
| backend liveness | compose healthcheck 内置：`urllib.request.urlopen('http://127.0.0.1:8000/healthz')` | 30s 间隔、3 次重试 |
| worker liveness | compose healthcheck：`celery ... inspect ping` → `pong` | 同上 |
| 应用健康（HTTP） | `curl -fsS http://127.0.0.1:8000/healthz` | `{"status": "ok", "app": "A3 Learning Agent System"}` |

**本机演练记录（2026-10-25）**：离线环境下以 TestClient 直调应用健康面——
`GET /healthz` → **`200 {'status': 'ok', 'app': 'A3 Learning Agent System'}`**，`HEALTHZ_EXIT=0`
（空库启动时按设计降级：BKT/RAG 记录"表不存在→内存/JSON 降级"warning，不影响健康面；
生产为 PG + 迁移先行，不会出现该降级）。**真实容器的 healthz 未验证。**

## 3. TLS / 域名（模板，未验证）

```nginx
# 反向代理示意（未在本机或任何主机上执行过）
server {
  listen 443 ssl;
  server_name <你的域名>;
  ssl_certificate     /etc/letsencrypt/live/<域名>/fullchain.pem;   # 证书获取方式未演练
  ssl_certificate_key /etc/letsencrypt/live/<域名>/privkey.pem;
  location / {
    proxy_pass http://127.0.0.1:5173;   # compose 默认仅发布 127.0.0.1:5173
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
  }
  # 后端 API 经同域反代或独立子域；CORS 由 A3_CORS_ORIGINS 控制（${VAR:?} 强制）
}
```

待办（人工）：域名/DNS、证书签发与续期（certbot 等）、`A3_CORS_ORIGINS` 生产值、
HSTS/安全头基线。**全部未验证。**

## 4. 迁移窗口（模板）

1. 窗口公告与停写（学生端停用窗口）；
2. 备份（§5）；
3. 单独执行迁移（对应 compose 的 `migrate` 服务；手动等价命令）：
   `docker compose ... run --rm migrate alembic upgrade head`；
4. 观察回执至 `head`（当前 12 个 revision，末位 `20261023_0012`）后放量；
5. 回滚：见 §6。

## 5. 备份 / 恢复（模板；SQLite 工具已在本机、PG 路径未验证）

| 场景 | 工具 | 状态 |
|---|---|---|
| SQLite（演示/单机） | `python scripts/backup_database.py --output data/backups/<ts>.db`，`--verify` 校验 | 脚本在仓库（sqlite3 online backup + integrity check）；**本机未跑**（本卡不动数据目录） |
| PostgreSQL（生产） | `pg_dump`/`pg_dumpall` 定时任务 + 卷快照（`postgres_data` volume） | **模板，未验证**；无仓库内脚本，属部署方职责 |
| Redis | AOF 已开（compose `--appendonly yes`）；快照可选 | 模板 |
| 恢复演练 | 停写 → 换卷/导入 → `alembic upgrade head` 校验版本表 → healthz → 冒烟 | **未演练** |
| 建议节奏 | 每日全量 + 迁移前强制一次；保留 ≥30 天；异机存放 | 待部署方确认 |

## 6. 回滚步骤（模板，未演练）

1. **应用回滚**：`git checkout <上一个已验收 main 提交>` → `docker compose ... up -d --build`；
   镜像化后改为回退镜像 tag（建议发行时打 `v1.0.0-rc1` 镜像标签，402 裁定）；
2. **数据库回滚**：优先**恢复备份**（比 downgrade 安全，迁移 downgrade 不承诺保留运行期数据）；
   仅当迁移本身需撤销时：`alembic downgrade <目标 revision>`（本机已验证 base 全链可逆，见 §8）；
3. **回滚后验证**：healthz + 学生端提问冒烟 + `docker compose logs backend --tail 100` 无迁移错误。

## 7. 监控接入（QWEN-341 指标与告警的落位）

| 项 | 落位 | 状态 |
|---|---|---|
| 指标暴露 | 既有 `GET /metrics`（Prometheus text exposition；production 仅 teacher/admin bearer 可读——无 token 401/学生 403/teacher 200） | 代码已交付；**Prometheus 抓取端未部署/未验证** |
| Run 指标 | `learning_runs_total{mode,status}`、`learning_run_duration_seconds`、`learning_run_errors_total{code}`、`learning_tool_calls_total`、`queue_claimed_total`、`learning_queue_pending_runs`、`quota_rejected_total{dimension}`、`run_cost_yuan_total`、`run_cost_unknown_runs_total`（9 个，`backend/app/services/run_metrics.py`） | 已交付 |
| 告警规则 | [docs/alerts_learning_runs.yml](alerts_learning_runs.yml) 6 条草案（成功率/错误率/队列积压/配额 429/unknown 成本占比/成本日耗）——**复制进真实 Prometheus rule set 前需部署方确认阈值** | 草案，未接 Alertmanager |
| Trace | Phoenix（compose 内网 `http://phoenix:6006`，OTLP endpoint 已配）；生产是否对外发布由部署方裁定 | 模板 |
| 进程内口径注意 | 指标为 telemetry 单例，多 worker 由 Prometheus 抓取侧按实例聚合 | 已登记（台账 §43.2） |
| 配额拒绝告警 | `sum(rate(quota_rejected_total[5m])) > 1` 对应 429 语义（`quota_exceeded`） | 草案 |

## 8. 本机演练记录（真实回执，2026-10-25）

| # | 演练 | 命令/口径 | 结果 |
|---|---|---|---|
| D1 | 应用健康面 | TestClient `GET /healthz`（离线环境） | **200** `{'status': 'ok', 'app': 'A3 Learning Agent System'}`，`HEALTHZ_EXIT=0` |
| D2 | 迁移 upgrade | `DATABASE_URL=sqlite:///./output/qwen403/drill.db`（全新）→ `alembic upgrade head` | exit 0，12 revision 至 `20261023_0012`；**34 张表**，`user_memories`/`memory_events` 存在 |
| D3 | 迁移 downgrade | `alembic downgrade base` | exit 0，全链 12 步回滚；**4 张表**，两张记忆表消失（`DRILL_ROUNDTRIP_OK`） |
| D4 | 迁移再 upgrade | `alembic upgrade head` | exit 0，回到 34 表、两张记忆表回归；`DRILL_EXIT=0` |
| D5 | 备份/恢复 | — | **未演练**（SQLite 脚本未跑，避免触碰数据目录；PG 路径无本机环境） |

> D2-D4 与 201 时代的结论一致（隔离 SQLite 全链可逆）；生产 PostgreSQL 的迁移演练**未做**。

## 9. 未验证项清单（发布声明必带）

- [ ] 公网部署 / 域名 / DNS / TLS 证书签发与续期；
- [ ] `docker compose ... config` 渲染与真实容器启停（本机无 Docker daemon）；
- [ ] PostgreSQL 生产迁移（`migrate` 服务真实回执）、PG 备份/恢复演练；
- [ ] Prometheus/Alertmanager 真实抓取 `/metrics` 与告警规则装载；
- [ ] `manage_access` 建号/授权在生产容器内执行；
- [ ] 负载/容量基线（仓库有 `scripts/load_test.py`，本卡未跑）；
- [ ] 独立复核 QWEN-404（P0，必须由未参与开发者执行——Lead/Trae/Qwen 自查不算）。
