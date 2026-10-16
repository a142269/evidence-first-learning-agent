# Docker 端到端冒烟指引（A2 任务）

> 用途：演示日前用本指引跑一遍完整 Docker 部署 + 端到端冒烟
> 触发：6/24-6/30 任意时段，每周至少跑 1 次
> 红线：演示日 7/22 必须用 docker-compose 跑通

---

## 0. 前置

需要本地装好：
- **Docker Desktop** 4.20+（含 docker compose v2）
- **8 GB+ 内存**（Python 容器 + nginx 容器）
- **6 GB 磁盘空间**（python:3.12-slim ≈ 130MB + Vue build ≈ 200MB + 依赖）

验证：
```powershell
docker --version            # 应该 24.0+
docker compose version      # 应该 v2.20+
docker ps                   # 不应报错
```

---

## 1. 一键启动（约 5-10 分钟首次 build）

```powershell
cd f:\比赛\中软杯\A3

# 复制 .env（如已存在跳过）
copy .env.example .env

# 启动 backend + frontend 两个容器
docker compose up -d --build

# 看容器状态（应该都是 healthy）
docker compose ps
```

预期：
```
NAME           SERVICE    STATUS              PORTS
a3-backend     backend    Up (healthy)        0.0.0.0:8000->8000/tcp
a3-frontend    frontend   Up (healthy)        0.0.0.0:5173->5173/tcp
```

如 health 状态长时间 `starting`，看日志：
```powershell
docker compose logs backend  --tail 50
docker compose logs frontend --tail 50
```

---

## 2. 端到端冒烟（一行命令）

```powershell
# 给容器 5 秒预热（首次启动 RAG 加载约需 3-5s）
python -m scripts.docker_smoke --wait 5

# 预期: 9/9 通过 in ~3s
```

---

## 3. 期望输出

```
==============================================================================
 Docker Smoke Test
==============================================================================
  OK   backend /system/status 200                          [   12.3 ms]
  OK   cockpit 8 blocks present                            [  155.7 ms]  {'blocks': 9, 'user_id': 'demo-student-1'}
  OK   cockpit no widespread block errors                  [  142.4 ms]  {'errored_blocks': []}
  OK   /cockpit/schema 200                                 [    8.1 ms]  {'fields': 9}
  OK   /profile/{user_id} 200                              [   10.2 ms]
  OK   /knowledge-graph/stats 200                          [   12.8 ms]
  OK   /cognitive/forecast?... 200                         [   23.4 ms]
  OK   frontend root 200 + HTML                            [    5.7 ms]
  OK   frontend nginx → backend /api/v1/system/status      [    9.8 ms]
------------------------------------------------------------------------------
  9/9 checks passed
```

---

## 4. 人工 5 步走（评委演示路径预演）

容器起来后：

1. **浏览器打开** http://localhost:5173
2. **登录**: `counselor` / `123456`
3. **聊天**: 输入 "我是大二学生，想学 CNN，请讲解并出几道题"
4. **看资源**: 等待多智能体生成（应有 PPTX / Mermaid / Code 等）
5. **看 cockpit**: 直接访问 http://localhost:5173/cockpit（如前端已实现）或 http://localhost:8000/api/v1/cockpit/student/demo-student-1

---

## 5. 故障排查

### Q: backend 容器启动后立刻退出
**A**: 看日志 `docker compose logs backend --tail 100`，常见原因：
- `requirements.txt` 有包不兼容 Python 3.12 → 看是否需 pin 版本
- `data/seed.json` 等 demo 资产未 COPY 进容器（已在 Dockerfile 第 22 行显式 COPY）

### Q: cockpit 返回 200 但 forecast 块是 error
**A**: 正常，意味着 BKT 历史还没初始化（首次启动）。跑：
```powershell
docker compose exec backend python -m scripts.verify_demo_assets
```
让其触发一遍 demo 数据加载。再调 cockpit 即可。

### Q: frontend 容器 healthy 但浏览器打不开
**A**: 检查 5173 端口是否被占用 `netstat -ano | findstr 5173`，杀掉占用进程或改端口映射。

### Q: nginx 反代 API 404
**A**: 检查 frontend/Dockerfile 里 `proxy_pass http://backend:8000;` 的 service name 是否与 docker-compose.yml 的 `services.backend` 一致。

---

## 6. 关闭 / 清理

```powershell
# 停止但保留数据卷
docker compose down

# 完全清理（含 volumes 删 SQLite 缓存）
docker compose down -v

# 删 build cache
docker builder prune -f
```

---

## 7. CI 集成（W3 接入）

```yaml
# .github/workflows/docker.yml （示例）
- name: Build & up containers
  run: docker compose up -d --build
- name: Wait + smoke
  run: |
    python -m scripts.docker_smoke --wait 15 --json > smoke.json
    cat smoke.json
- name: Logs on failure
  if: failure()
  run: docker compose logs
```

---

## 8. 冒烟历史记录

| 日期 | 跑者 | 结果 | 备注 |
|------|------|------|------|
| 2026-06-24 | A | **脚本 7/7 通过 (uvicorn proxy)** | 用 `uvicorn --port 8800` 模拟容器 backend，docker_smoke.py 全过；counselor 登录返 token；接口契约已确认 |
| 2026-06-24 | A | docker compose 配置已就绪 | 修 `docker/Dockerfile` Py3.10→3.12 + 加 healthcheck；新写 `frontend/Dockerfile` (multi-stage nginx 含 API 反代)；新增 `.dockerignore` |
| 2026-07-04 | A | **Day 6 同源相对路径模式** 配置 | `http.ts` 支持 `VITE_API_BASE_URL=""` → 浏览器走 nginx 反代；`frontend/Dockerfile` 加 `ARG VITE_API_BASE_URL` build arg；`docker-compose.yml` 加 frontend service args `VITE_API_BASE_URL: ""` + 加 a3net network + backend depends_on healthcheck；nginx conf 加 `/healthz` 端点 + assets 1y 缓存 + SSE chunked_transfer_encoding off |
| _ | 用户 | 待用户实跑 9/9 | 见下文 §9 命令模板，跑完填本行 |

请用户跑过后在此表追加记录（A 本机无 docker daemon，只能保证 Dockerfile/脚本/接口契约正确）。

---

## 9. 用户实跑指令模板（W3 Docker 端到端验证）

> 前提：本机已装 Docker Desktop（Windows）或 docker engine + docker-compose-plugin（Linux）

```powershell
# === 1. 首次构建并启动两容器 ===
cd F:\比赛\中软杯\A3
docker compose up -d --build

# 期望输出：
#   [+] Building ...
#   [+] Running 3/3
#    ✔ Network a3_a3net      Created
#    ✔ Container a3-backend  Started
#    ✔ Container a3-frontend Started

# === 2. 等 12s 后跑 9 项冒烟 ===
python -m scripts.docker_smoke --wait 12

# 期望 9/9 通过：
#   OK   backend /system/status 200
#   OK   cockpit 8 blocks present
#   OK   cockpit no widespread block errors
#   OK   /cockpit/schema 200
#   OK   /profile/{user_id} 200
#   OK   /knowledge-graph/stats 200
#   OK   /cognitive/forecast?... 200
#   OK   frontend root 200 + HTML
#   OK   frontend nginx → backend /api/v1/system/status

# === 3. 浏览器验证 ===
# http://localhost:5173/         → 跳 /cockpit
# http://localhost:5173/cockpit  → 三栏完整渲染
# http://localhost:5173/api/v1/cockpit/student/demo-student-1 → JSON

# === 4. 跑完更新 §8 表 ===
# 把"待用户实跑"那行改为：
#   | 2026-07-XX | 用户 | 9/9 通过 + 浏览器 /cockpit 正常 | 首次 build 耗时 X 分钟 |

# === 5. 出问题时排查 ===
docker compose logs backend  --tail=50
docker compose logs frontend --tail=50
docker compose ps             # 看健康状态
```

### 常见问题

| 症状 | 原因 | 解决 |
|------|------|------|
| `Cannot connect to Docker daemon` | Docker Desktop 没启动 | 启动 Docker Desktop |
| frontend 启动但 /api/ 404 | nginx conf 反代地址错 | 确认 `frontend/Dockerfile` 内 nginx 配置 `proxy_pass http://backend:8000;`（service 名而非 localhost） |
| backend healthcheck 失败 | curl 缺失 / 端口未通 | docker exec 进 backend 容器 `curl http://localhost:8000/healthz` |
| docker_smoke 9 项里 frontend 2 项失败但 backend 7 项过 | nginx 还在启动 | 加 `--wait 20` 多等几秒 |
| 浏览器 /cockpit 显示空白 + 控制台 CORS 错 | 同源模式没生效 | 检查 dist 里 JS chunk grep `VITE_API_BASE_URL` 是否被 build 时替换为 `""`；如果还是 `127.0.0.1:8000`，重 build：`docker compose build --no-cache frontend` |
