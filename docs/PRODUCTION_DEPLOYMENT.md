# 生产部署（Production Deployment）

> 状态：生产部署配方与预检已提供，但**尚未在本机 Docker 引擎上实际启动验证**，也未在远端 CI 验证。演示/离线使用请继续阅读 README 与 [Docker 冒烟指南](DOCKER-SMOKE-GUIDE.md)。

## 1. 与演示部署的区别

仓库里有三套 Compose 用法：

| 配方 | 用途 | 安全边界 |
| --- | --- | --- |
| `docker-compose.yml` | 本地/离线演示（两容器） | `APP_ENV` 未设置 = 开发模式：V1 演示路由开放、内置演示账号可用 |
| `docker-compose.yml` + `docker-compose.enterprise.yml` | 企业本地演示（PostgreSQL/Redis/Phoenix/Celery） | 仍是开发模式；**不要**把它当作可联网生产部署 |
| `docker-compose.production.yml` | 生产边界（本文件） | `APP_ENV=production`：V1 仅白名单、隐藏内置账号与 `/docs`、`/metrics` 需教师/管理员、启动时强制校验配置 |

`docker-compose.production.yml` 是一个**独立文件**（不是 overlay），不会与演示配置混用。

## 2. 准备

1. 复制模板并替换全部 `REPLACE_WITH_*`：`cp .env.production.example .env.production`。
2. 生成强随机的 `POSTGRES_PASSWORD` / `PHOENIX_DB_PASSWORD`（≥12 字符）与模型 API Key；不要提交 `.env.production`。
3. 设置 `A3_CORS_ORIGINS` 为真实的 **https** 前端来源。
4. 将前端暴露端口（默认 `127.0.0.1:5173`）放在 TLS 反向代理之后。

生产启动会执行 `validate_deployment()`：数据库密码过短或含 `REPLACE/change-me/example`、CORS 非 https、缺少模型配置等都会**失败关闭**，不会带着占位值启动。

## 3. 启动

```bash
# 仅校验配置（不需要 Docker 引擎）
docker compose --env-file .env.production -f docker-compose.production.yml config

# 启动（需要 Docker 引擎与本机镜像/构建能力）
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

启动顺序由 `depends_on` 保证：postgres healthy → migrate（`alembic upgrade head`）完成 → backend healthy → frontend 启动。

## 4. 初始化账号与课程授权

生产模式禁用内置演示账号与教师自助注册，只用可信主机 CLI 创建账号：

```bash
# 创建教师账号（交互式输入 12+ 字符密码，不回显）
docker compose --env-file .env.production -f docker-compose.production.yml \
  exec backend python -m scripts.manage_access create-teacher <account>

# 授予课程访问（V2 生产模式按数据库课程授权）
docker compose --env-file .env.production -f docker-compose.production.yml \
  exec backend python -m scripts.manage_access grant <account> --course <course_id>
```

学生账号可通过 `/api/v1/auth/register` 自助注册（生产模式仅允许 student 角色），随后同样需要课程授权。

## 5. 生产模式会关闭/限制什么

- V1 遗留接口：只放行显式白名单（`backend/app/core/v1_production_access.py`，11/182 项操作），其余返回 403；V1 WebSocket 在生产模式直接拒绝。
- 内置演示账号与教师自助注册关闭。
- `/docs`、`/redoc`、`/openapi.json` 返回 404；`/metrics`、`/metrics/llm-cost` 需要教师/管理员登录。
- 数据库/Redis/Phoenix 不在宿主机发布端口；仅前端端口（默认回环）发布。
- 会话记忆、课程权限、运行所有者在生产模式均按账号/课程校验。

## 6. 验证清单

- [ ] `docker compose ... config` 退出码 0，且输出里没有占位凭据。
- [ ] 后端容器 `/healthz` 返回 200；`docker compose ps` 全部 healthy。
- [ ] `GET /docs` 与 `/openapi.json` 返回 404；匿名 `GET /metrics` 返回 401。
- [ ] 生产模式下匿名访问 `/api/v1/resources/list` 返回 401；学生 token 访问其他用户资源被拒绝。
- [ ] `alembic current` 为 head；PG 扩展 `vector` 存在。
- [ ] 教师审核、运行恢复与 SSE 在真实 PostgreSQL 下完成一次人工走查（尚未在本机验证）。
- [ ] 备份/恢复与 TLS 由部署方负责；本仓库不包含备份编排。

## 7. 尚未完成 / 限制

- **未启动完整生产栈**：`docker-compose.production.yml` 的 `up` 与后端镜像构建未在本机实际执行；`docker compose config` 仅证明配置可解析。
- 已验证部分真实数据库路径（2026-10-18）：用一次性隔离容器（本机已有 `pgvector/pgvector:pg16`、`redis:7-alpine` 镜像，未拉取）跑通 Alembic `upgrade head → downgrade base → upgrade head`、pgvector 扩展、33 文件企业合同测试（353 passed）以及部分完成学习包在真实 PostgreSQL 检查点上的跨进程恢复；但这不等于生产栈、TLS、Phoenix、备份与部署窗口验收。
- 第三方许可/NOTICE 见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)（机器生成，非法律意见）；GPL/LGPL 与无来源素材需人工审查。
- Phoenix 镜像默认 `latest`，正式部署前应固定经审核的 tag。
- 监控/告警、日志聚合、备份、TLS 与密钥管理属于部署方职责。
