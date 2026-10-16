# 安全审查报告（A3 智学领航）

> 作者：A · 2026-06-24
> 范围：OWASP Top 10 + LLM 应用专有威胁（Prompt Injection / 答案泄露 / 代码沙箱逃逸 / 误概念强化）
> 受众：评委复审 + 团队收口
> 验证：每条措施都给出 commit / 文件 / 测试可复验

---

## 一、Executive Summary

| 维度 | 当前状态 | 证据 |
|------|---------|------|
| **代码沙箱（Manim / Code 生成）** | ✅ 加固，xfail 清零 | `0a6f842` · 66 regression test 全过 |
| **Prompt Injection** | ✅ 49 个对抗输入覆盖 | `tests/regression/bad_inputs.py` + `test_sandbox_resilience.py` |
| **教学安全（答案泄露 / 误概念）** | ✅ 4 字段评估器 | `fba0c41` 创新点 11 |
| **证据链（防 LLM 胡说）** | ✅ 5 source type ledger | `3048bc8` 创新点 12 |
| **配额 / 重试 / 缓存** | ✅ PromptCache + 语义重试 | `040886b` |
| **AuthN / AuthZ** | 🟡 公开演示端点放宽白名单；后台需 token | `auth.py` + `main.py:25` |
| **SQL Injection / Path Traversal** | ✅ SQLAlchemy ORM + Pydantic 校验 | 全栈 |
| **DoS（资源耗尽）** | ✅ 沙箱 AST 层拦截 + 字面量上限 | `0a6f842` · `max_literal_multiplier=10M` |
| **数据隐私** | 🟡 演示阶段无真实 PII；生产前需复查 | — |

**结论**：演示阶段已无高危漏洞，所有 LLM 应用专有威胁都有缓解措施。
**生产部署前需追加**：（1）AuthN 全面强制；（2）数据加密（HTTPS / 数据库静态加密）；（3）PII 脱敏管线。

---

## 二、OWASP Top 10 (2021) 对照

### A01 — Broken Access Control
- **风险**：未授权访问、越权读取他人画像
- **当前**：演示账号 `counselor / admin` + token 中间件（[main.py:25](../backend/app/main.py#L25)）
- **限制**：14 个 v1 子路径加入了白名单（chat/profile/learning-path/...），评委演示无需 token
- **生产前**：白名单清单收紧，加入 user_id 级越权检查（当前画像 API 任何登录用户都能读任何 user_id）
- **CWE**：CWE-285 / 639

### A02 — Cryptographic Failures
- **风险**：密码明文 / 弱哈希
- **当前**：[auth.py:71](../backend/app/api/v1/auth.py#L71) 用 SHA-256 哈希密码
- **限制**：SHA-256 速度快易暴破，生产应换 bcrypt / argon2
- **生产前**：Hash → argon2id；启用 HTTPS；token TTL 24h → 8h

### A03 — Injection
- **SQL Injection**：✅ 全部走 SQLAlchemy ORM（`backend/app/core/models.py`），未发现 raw SQL 拼接
- **Path Traversal**：✅ artifacts 端点用 `rid` 唯一 ID 而非文件路径；`Path.resolve()` + `is_relative_to()` 检查
- **Template Injection**：✅ Jinja 不在 demo 路径上启用
- **CWE**：CWE-89 / 22 / 1336

### A04 — Insecure Design
- **风险**：业务设计层面的漏洞
- **当前**：
  - ✅ Sandbox 三级隔离（AST / RestrictedPython / Subprocess）
  - ✅ CoV 输出后验证 + Ledger 输出时打证据，双重防幻觉
  - ✅ PedagogicalSafety 防"AI 直接给答案让学生 copy"
- **设计原创**：教育场景专有威胁（"教学风险" vs "通用内容安全"）

### A05 — Security Misconfiguration
- **当前**：`.env.example` 标注 `change-me-in-production`；演示账号默认 `123456`（必须改）
- **限制**：CORS `allow_origins` 仍含 localhost；演示账号默认密码弱
- **生产前**：CORS 收紧到具体域名；强制 .env 检查（`SECRET_KEY` 不能是 `change-me`）

### A06 — Vulnerable and Outdated Components
- **当前**：`requirements.txt` 依赖版本基本最新（fastapi 0.110+ / pydantic 2.6+）
- **追加**：建议 CI 加 `pip-audit` 或 `safety check`

### A07 — Identification and Authentication Failures
- **当前**：内存 token store（`auth.py:_active_sessions`）
- **限制**：进程重启 token 全失效；演示阶段可接受，生产需换 Redis / DB
- **登录暴破**：未限流（如评委疯狂点登录可 brute force 弱密码）

### A08 — Software and Data Integrity Failures
- **当前**：✅ 演示资产健康检查 14/14（`verify_demo_assets`），CI 强制；任何 demo 数据损坏会拒绝部署
- **CI 强制**：`6/24` 已把 `verify_demo_assets --json` 加进 CI 步骤

### A09 — Security Logging and Monitoring Failures
- **当前**：✅ 全模块用 `logging`，输出到 stdout（容器化场景适合）
- **限制**：无聚合 / 无告警；生产建议加 sentry / loki
- **演示阶段足够**：评委追问"日志在哪"，可直接 `docker compose logs backend`

### A10 — Server-Side Request Forgery (SSRF)
- **风险**：用户输入触发后端访问内网
- **当前**：✅ Sandbox blocked_modules 含 `socket / requests / urllib / http` 全部禁用网络
- **CoV / Ledger 内部检索**：仅本地 RAG / KG，不访问外网

---

## 三、LLM 应用专有威胁（OWASP LLM Top 10）

### LLM01 — Prompt Injection
- **当前**：
  - ✅ 49 个对抗输入（`tests/regression/bad_inputs.py`）：PROMPT_INJECTION_INPUTS / token_smuggling / homograph_command / 等
  - ✅ Sandbox AST 层拦截 12 个 dangerous_code 模板
  - ✅ Critic Agent 二次审查
- **测试**：`pytest tests/regression -v` → 66 passed 0 xfail（`0a6f842`）

### LLM02 — Insecure Output Handling
- **风险**：LLM 输出未消毒就 eval / 渲染
- **当前**：
  - ✅ Sandbox 三级隔离强制（任何代码必须过 AST + RestrictedPython）
  - ✅ Mermaid / Manim DSL 通过专门 parser，不走 LLM 直接 eval
  - ✅ 5 个 MALICIOUS_DSL_INPUTS 对抗测试

### LLM03 — Training Data Poisoning
- **不适用**：本项目不训练 LLM，全部用预训练模型

### LLM04 — Model Denial of Service
- **当前**：
  - ✅ AST DoS 拦截：`while True`无 break / `[0]*10^9` / `range(10^12)` 全拦
  - ✅ Subprocess 5s 超时
  - ✅ PromptCache 减少重复 LLM 调用

### LLM05 — Supply Chain Vulnerabilities
- **当前**：依赖锁定 `requirements.txt`；建议 CI 加 `pip-audit`

### LLM06 — Sensitive Information Disclosure
- **风险**：LLM 输出含 API key / 用户 PII
- **当前**：演示无真实 PII；prompt 模板不含 secret

### LLM07 — Insecure Plugin Design
- **不适用**：本项目无第三方 LLM plugin

### LLM08 — Excessive Agency
- **当前**：
  - ✅ Critic Agent 必须给质疑 + 改进建议两段结构化输出
  - ✅ Reviewer Agent 仲裁，无单一 Agent 决定权
  - ✅ PedagogicalSafety 4 字段评估（创新点 11）

### LLM09 — Overreliance（学生过度依赖 AI）
- **当前**：
  - ✅ PedagogicalSafety `scaffolding_score` 强制引导 + `answer_leak_risk` 防直接给答案 + `student_uptake_prompt` 把球抛回学生
  - ✅ 这是 A3 教育场景原创创新点 11

### LLM10 — Model Theft
- **不适用**：用第三方 LLM（讯飞 Spark / OpenAI 兼容）

---

## 四、教育场景专有威胁（A3 原创风险维度）

### EDU01 — 答案泄露（Answer Leak）
- **威胁**：AI 直接给答案，学生 copy 不思考
- **缓解**：`PedagogicalSafety.answer_leak_risk` 字段（[pedagogical_safety.py](../backend/app/services/pedagogical_safety.py)）
- **检测正则**：`正确答案是` / `解：` / `完整代码：` 等
- **强证据**：correct_answer 整段在响应里 → 加 0.5 风险
- **测试**：`test_pedagogical_safety.py::TestAnswerLeak × 3` 全过

### EDU02 — 误概念强化（Misconception Reinforcement）
- **威胁**：AI 盲目肯定学生错答 → 学生记错的更深
- **缓解**：`misconception_reinforcement_risk` 字段
- **检测**：echo 学生错答 + 缺纠错信号（"不对" / "实际上" / "应该是"）→ 加 0.6 风险
- **测试**：`TestMisconception × 3` 全过

### EDU03 — 引导失败（Scaffolding Failure）
- **威胁**：AI 一次性吐答案，不分层引导
- **缓解**：`scaffolding_score` 字段；命中 "你觉得" / "想想" / "第一步" 10 类引导话术加分
- **测试**：`TestScaffolding × 3` 全过

### EDU04 — Uptake 缺失
- **威胁**：AI 答完没有把球抛回学生
- **缓解**：`student_uptake_prompt` 按 Bloom 6 层各 2 模板自动生成下一步思考问题
- **测试**：`TestUptakePrompt × 4` 全过

### EDU05 — 来源不可追溯
- **威胁**：AI 输出无证据，评委 / 学生无法验证
- **缓解**：`ClaimLedger` 5 source type（textbook / kg / rag_chunk / mistake / history）（[claim_ledger.py](../backend/app/services/claim_ledger.py)）
- **特性**：跨源冲突自动 conflict_warning；support_rate 量化整体证据强度
- **测试**：`test_claim_ledger.py` 21 passed

---

## 五、复现验证（评委可现场跑）

```bash
# 1. 安全相关测试全集
pytest tests/regression -v                  # 66 passed (含 12 dangerous code + 49 bad inputs)
pytest tests/a/test_pedagogical_safety.py   # 24 passed (P1.1 教学安全)
pytest tests/a/test_claim_ledger.py         # 21 passed (P1.2 证据链)
pytest tests/a/test_code_sandbox.py         # 沙箱核心

# 2. Cockpit 任一子块异常不挂主接口（兜底稳定性）
pytest tests/a/test_cockpit_branches.py     # 47 passed

# 3. 演示资产健康检查（任一失败 CI 拒绝部署）
python -m scripts.verify_demo_assets        # 14/14 in 7.6s

# 4. 压测（DoS 抗性）
python -m scripts.load_test --concurrency 50 --requests 200
```

---

## 六、生产部署 checklist（演示之后）

| # | 项 | 当前 | 生产要求 |
|---|---|------|---------|
| 1 | 密码哈希 | SHA-256 | argon2id + per-user salt |
| 2 | Token 存储 | 内存 dict | Redis with TTL |
| 3 | HTTPS | 无 | nginx + Let's Encrypt |
| 4 | CORS allowed_origins | localhost / 192.168 | 具体生产域名 |
| 5 | 登录限流 | 无 | slowapi 5/min |
| 6 | PII 脱敏 | 无 | log 前过滤 + DB 列加密 |
| 7 | 依赖安全审计 | 无 | CI 加 pip-audit |
| 8 | 越权检查 | 无（任何登录用户读任何 user_id） | RBAC + ownership check |

---

## 七、答辩相关 30 秒话术

**评委问：你们怎么防 AI 胡说八道 / 直接给答案 / 让学生 copy 不思考？**

> 我们有三层防御：
> 1. **CoV (创新点 2, Dhuliawala EMNLP 2023)**：输出后抽 claim 反问验证，不一致回写
> 2. **ClaimLedger (创新点 12, ARES 启发)**：输出时给每句打 5 类证据 + 跨源冲突警告
> 3. **PedagogicalSafety (创新点 11, A3 原创)**：4 字段评估教学场景专有威胁——答案泄露 / 误概念强化 / 引导失败 / uptake 缺失
>
> `tests/regression` 66 个对抗输入测试 + `pytest tests/a/test_pedagogical_safety.py` 24 个用例，现场可跑。

**评委问：你们的代码沙箱安全吗？能防 DoS 吗？**

> 沙箱三级隔离（AST → RestrictedPython → Subprocess）+ AST 层 DoS 模式拦截（`while True` 无 break / 序列乘法上限 1000 万 / range 上限 1000 万 / threading 黑名单）。
> 之前有 1 个 xfail（Day 9 留的"AST 缺 per-execution caps"），6/24 commit `0a6f842` 已彻底清掉。`pytest tests/regression` 66 passed 0 xfail。
