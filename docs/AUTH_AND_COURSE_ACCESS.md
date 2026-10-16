# 登录持久化与 V2 课程授权

2026-10-14：复用原登录响应与学生/教师角色，新增持久化会话、密码升级和逐账号课程授权。本次没有修改用户密钥、没有迁移业务库。

同日补充：登录按账号摘要维护 15 分钟失败窗口，第 5 次错误后临时限流；成功登录清除计数。`AuthRepository.cleanup_expired()` 可清理过期 Session 与旧限流记录，签发新 Session 时也清理过期 Session。新增 `20261014_0011_login_attempts` 迁移。限流不代替网关/IP 级防护。

## 已实现契约

- 登录令牌使用 32 随机字节生成；数据库 auth_sessions 只保存 SHA-256 摘要，原令牌只返回客户端。默认 1 天，remember 为 7 天。每次鉴权读取数据库，重启、多个应用进程不依赖共享内存。
- 注销删除对应会话。重置密码、更改角色及删除账号撤销关联会话；删除账号同时删除课程授权。令牌过期、已撤销或权限库不可用时拒绝请求，数据库异常正文不发给客户端。
- 注册及恢复密码使用 PBKDF2-HMAC-SHA256、600000 次迭代、独立随机盐。已有 SHA-256 密码只在成功验证后升级；升级与会话创建同一事务。登录签发以原密码哈希为条件锁定账号，避免并发重置后签发旧凭据会话。
- 注册使用仅新增语义；并发同名注册不能覆盖已有密码或角色。生产模式拒绝公开注册教师，教师由可信宿主机 CLI 创建。
- course_grants 保存 account/course_id。学生只能读取自己的 Run，教师只能审核被授予课程中的 Run；请求体不能伪造用户身份。创建、查询、事件、审核及修复复用 V2 授权检查。
- APP_ENV=production 强制登录及数据库课程授权，并拒绝开发模式签发的内置账号会话。生产 V1 只开放精确方法和路径的兼容清单：登录、注册、当前账号、注销、已发布课程目录、资源类型，以及学生的资源列表、详情、附件下载、保存和删除。其余旧路由返回 403 `v1_route_unavailable_in_production`；未知新路由默认关闭。开发模式原公开前缀保留。没有课程授权的新账号不能读取对应的课程资源。
- V1 `/resources/save` 使用登录会话确定学生资源所有者，拒绝伪造其他账号及课程发布/学生指派范围；`DELETE /resources/{id}` 只允许学生删除自己的个人资源。学生资源列表、详情和附件下载在生产模式查 `course_grants`，撤销后立即拒绝；教师草稿和非目标学生不能通过资源所有者字段提前查看。此前独立 SQLite 的真实登录/授予/撤销及资源、教师协作、移动端组合 55 项通过。生产路由收敛后，V1 教师管理、知识库上传和旧学生数据页面暂不可用；这些页面需逐路由完成账号及课程授权后再进入兼容清单。V2 课程授权与 Run 工作流不受该清单限制。
- 生产以外默认保留 V2_COURSE_AUTH_MODE=environment 的演示白名单；可显式设为 database 验证逐账号权限。数据库模式不接受匿名请求，数据库失败不会退回环境变量白名单。

## 部署与账号配置

先在目标部署的维护窗口运行迁移，再启动更新后的服务。企业 Compose 的 migrate 服务已有 `alembic upgrade head`，backend 等待它成功。现有环境需确保 migrate 使用新镜像重新执行，不仅重启旧 backend。20261014_0008 新增会话与授权表，并兼容历史 create_all 创建的账号表。

可信宿主机已显式设置目标 DATABASE_URL、安装依赖并完成迁移后，在项目根目录执行：

```powershell
python -m scripts.manage_access create-teacher instructor --display-name '课程教师'
python -m scripts.manage_access grant instructor --course artificial_intelligence
python -m scripts.manage_access grant student-account --course artificial_intelligence
python -m scripts.manage_access revoke student-account --course artificial_intelligence
```

教师密码从隐藏终端提示输入两次，不提供命令行密码参数；已有同名账号不会覆盖。学生须先完成注册，grant 不自动创建账号。课程撤销从后续请求生效；不会自动取消已通过鉴权、正在执行的外部模型请求。

兼容变化：部署后原进程内令牌不能迁移，用户需要重新登录一次。新令牌此后可以跨应用重启使用。将环境设为 production 前需显式准备教师账号及课程授权；默认演示账号不能用于生产。迁移回退会删除新会话/授权表，保留账号及已升级密码；旧代码不支持新密码格式，不能直接回退到旧 SHA-256 登录实现。

## 验证与范围

```powershell
python -m pytest tests/a/test_persistent_auth.py tests/a/test_auth_migration.py tests/a/test_auth_restart.py tests/a/test_registered_account_persistence.py tests/a/test_registration_onboarding.py tests/a/test_student_data_deletion.py tests/a/test_v2_access.py tests/a/test_deployment_policy.py --no-cov --benchmark-disable -q
```

test_auth_restart.py 覆盖 SQLite 和显式配置的一次性 PostgreSQL：进程 A 使用真实密码登录，进程 B 使用原 token 调用真实 /auth/me 和 V2 Run 查询，然后撤销课程授权与登出并验证 403/401。身份、密码验证与课程授权均未替换为测试桩；保存的 Run 是测试数据，没有模型执行。PostgreSQL 情况由 TEST_V2_POSTGRES_URL 启用；未配置时跳过，不能计为验收通过。API 在进程内运行，并未经过真实反向代理或 HTTPS。

2026-10-14 实际结果：持久化认证 17 项，原账号/注册/删除/V2 权限/部署策略 21 项；迁移 2 项、SQLite/PostgreSQL 跨进程认证 2 项均通过。它们分别包含在 final.xml 的 43 项与 integration.xml 的 48 项相关回归中，报告位于 output/auth-20261014，不能将这两个测试批次当作云端质量指标。

本轮尚未完成：OIDC、登录限流/锁定策略、会话管理页面、过期会话定期清理、V1 全量接口资源级隔离，以及真实身份与云端模型共同参与的完整端到端验收。V2 课程授权不代表所有旧 V1 演示接口已完成企业权限治理。浏览器仍沿用原有 Bearer token 存储方式，尚未迁移 HttpOnly Cookie。

真实云端模型/Embedding 验收需事先授权并产生费用。本机临时数据、报告、浏览器截图不提交。
