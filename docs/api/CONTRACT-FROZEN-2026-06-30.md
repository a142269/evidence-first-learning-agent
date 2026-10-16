# API 契约冻结审查（W1 → W2 前哨）

> **状态**: 🔒 **已冻结 2026-06-30**（A 单方完成仪式，B 待补签字）
> **审查人**: A + B（双方签字才完整冻结）
> **冻结后红线**: 任何字段变更必须 A+B 双方同意 + 必须先发 issue
> **依据**: [开发日志/2026-06-24-A-双人开发计划.md](../../开发日志/2026-06-24-A-双人开发计划.md) §七 / [开发日志/2026-06-25-A-前端启动双人开发计划.md](../../开发日志/2026-06-25-A-前端启动双人开发计划.md) §八 / [开发日志/2026-06-29-A-给B的Phase1Day1实测清单.md](../../开发日志/2026-06-29-A-给B的Phase1Day1实测清单.md)
> **配套交付**: [docs/api/COMPONENT-CONTRACT.md](COMPONENT-CONTRACT.md) · [docs/api/cockpit-endpoint.md](cockpit-endpoint.md)

---

## 1. 冻结目的

W2 (7/01-) 起前端 CockpitView 启动；如果后端字段名 / 类型 / 必选性还在漂移，
前端会被反复重写。本审查把 W1 末（6/30）那一刻所有评委可能触达的接口字段
钉死，给前端一份稳定的"圣经"。

---

## 2. 全部 API 路由清单（84 路由 / 16 子模块）

### 2.1 Auth (3)

| Method | Path | 用途 | 冻结状态 |
|--------|------|------|---------|
| POST | `/api/v1/auth/login` | 登录 | ✅ 已稳定 |
| POST | `/api/v1/auth/logout` | 登出 | ✅ |
| GET  | `/api/v1/auth/me` | 当前用户 | ✅ |

### 2.2 Chat (8)

| Method | Path | 冻结 |
|--------|------|-----|
| POST | `/api/v1/chat/send` | ✅ |
| POST | `/api/v1/chat/stream` | ✅ |
| POST | `/api/v1/chat/with-cov` | ✅ |
| POST | `/api/v1/chat/clear` | ✅ |
| GET  | `/api/v1/chat/cov-demo-cases` | ✅ |
| GET  | `/api/v1/chat/history/{session_id}` | ✅ |
| GET  | `/api/v1/chat/profile/{session_id}` | ✅ |
| GET  | `/api/v1/chat/realtime/{session_id}` | ✅ |

### 2.3 Profile (4)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/profile/dimensions` | ✅ |
| GET  | `/api/v1/profile/{user_id}` | ✅ |
| POST | `/api/v1/profile/{user_id}/update` | ✅ |
| POST | `/api/v1/profile/{user_id}/reset` | ✅ |

### 2.4 Resources (4)

| Method | Path | 冻结 |
|--------|------|-----|
| GET    | `/api/v1/resources/list` | ✅ |
| GET    | `/api/v1/resources/types` | ✅ |
| POST   | `/api/v1/resources/save` | ✅ |
| GET    | `/api/v1/resources/{resource_id}` | ✅ |
| DELETE | `/api/v1/resources/{resource_id}` | ✅ |

### 2.5 Learning Path (4)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/learning-path/list` | ✅ |
| GET  | `/api/v1/learning-path/{path_id}` | ✅ |
| POST | `/api/v1/learning-path/save` | ✅ |
| POST | `/api/v1/learning-path/{path_id}/progress` | ✅ |

### 2.6 Assessment (2)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/assessment/{user_id}` | ✅ |
| POST | `/api/v1/assessment/{user_id}/record` | ✅ |

### 2.7 Knowledge (3)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/knowledge/courses` | ✅ |
| GET  | `/api/v1/knowledge/status` | ✅ |
| POST | `/api/v1/knowledge/index/{course_name}` | ✅ |

### 2.8 Artifacts (16)

| Method | Path | 冻结 |
|--------|------|-----|
| POST | `/api/v1/artifacts/generate/code` | ✅ |
| POST | `/api/v1/artifacts/generate/manim` | ✅ |
| POST | `/api/v1/artifacts/generate/mermaid` | ✅ |
| POST | `/api/v1/artifacts/generate/mermaid-code` | ✅ |
| POST | `/api/v1/artifacts/generate/multi` | ✅ |
| POST | `/api/v1/artifacts/generate/pptx` | ✅ |
| POST | `/api/v1/artifacts/generate/tts` | ✅ |
| GET  | `/api/v1/artifacts/list` | ✅ |
| GET  | `/api/v1/artifacts/info/{rid}` | ✅ |
| GET  | `/api/v1/artifacts/tts/voices` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/data-uri` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/manim` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/mermaid` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/mp3` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/png` | ✅ |
| GET  | `/api/v1/artifacts/{rid}/pptx` | ✅ |

### 2.9 Metrics (3)

| Method | Path | 冻结 |
|--------|------|-----|
| GET | `/api/v1/metrics` | ✅ |
| GET | `/api/v1/metrics/health` | ✅ |
| GET | `/api/v1/metrics/summary` | ✅ |

### 2.10 System (3)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/system/status` | ✅ |
| GET  | `/api/v1/system/variant/demo-samples` | ✅ |
| POST | `/api/v1/system/variant/{mistake_id}` | ✅ |

### 2.11 Mistakes (9)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/mistakes/categories` | ✅ |
| GET  | `/api/v1/mistakes/heatmap` | ✅ |
| GET  | `/api/v1/mistakes/{user_id}` | ✅ |
| GET  | `/api/v1/mistakes/{mistake_id}/attribution` | ✅ |
| POST | `/api/v1/mistakes/record` | ✅ |
| POST | `/api/v1/mistakes/{mistake_id}/analyze` | ✅ |
| POST | `/api/v1/mistakes/{mistake_id}/remediation` | ✅ |
| POST | `/api/v1/mistakes/{mistake_id}/resolve` | ✅ |
| POST | `/api/v1/mistakes/{mistake_id}/variants` | ✅ |

### 2.12 Cognitive (10)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/cognitive/bkt/{user_id}` | ✅ |
| GET  | `/api/v1/cognitive/bloom/detail` | ✅ |
| GET  | `/api/v1/cognitive/bloom/levels` | ✅ |
| GET  | `/api/v1/cognitive/counterfactual` | ✅ B 6/23 落地 |
| GET  | `/api/v1/cognitive/forecast` | ✅ |
| POST | `/api/v1/cognitive/bkt/update` | ✅ |
| POST | `/api/v1/cognitive/bloom/classify` | ✅ |
| POST | `/api/v1/cognitive/diagnose` | ✅ |
| POST | `/api/v1/cognitive/next-best-question` | ✅ |
| POST | `/api/v1/cognitive/reverse-plan` | ✅ |

### 2.13 Knowledge Graph (7)

| Method | Path | 冻结 |
|--------|------|-----|
| GET | `/api/v1/knowledge-graph/3d` | ✅ |
| GET | `/api/v1/knowledge-graph/kps` | ✅ |
| GET | `/api/v1/knowledge-graph/kps/{kp_id}` | ✅ |
| GET | `/api/v1/knowledge-graph/lookup` | ✅ |
| GET | `/api/v1/knowledge-graph/neighbors` | ✅ |
| GET | `/api/v1/knowledge-graph/search` | ✅ |
| GET | `/api/v1/knowledge-graph/stats` | ✅ |

### 2.14 Gamification (4)

| Method | Path | 冻结 |
|--------|------|-----|
| GET  | `/api/v1/gamification/{user_id}` | ✅ |
| POST | `/api/v1/gamification/{user_id}/xp` | ✅ |
| POST | `/api/v1/gamification/{user_id}/checkin` | ✅ |
| POST | `/api/v1/gamification/{user_id}/achievement` | ✅ |

### 2.15 Social (2)

| Method | Path | 冻结 |
|--------|------|-----|
| GET | `/api/v1/social/peer-suggestions` | ✅ |
| GET | `/api/v1/social/tutor-suggestions` | ✅ |

### 2.16 Cockpit (2) ⭐ 新增 6/24

| Method | Path | 冻结 |
|--------|------|-----|
| GET | `/api/v1/cockpit/student/{user_id}` | ✅ 6/24 落地 |
| GET | `/api/v1/cockpit/schema` | ✅ 6/24 落地 |

---

## 3. Cockpit 字段表（前端最重要 — 9 字段）

详见 [cockpit-endpoint.md](cockpit-endpoint.md)，此处复述顶层 schema：

| Key | 类型 | 来源 | 失败兜底 |
|-----|------|------|---------|
| `user_id` | str | echo | 必填 |
| `generated_at` | str ISO8601 | server 时间戳 | 必填 |
| `profile` | obj | profile API + seed 兜底 | `{"error": ..., "radar_6d": [0.5]*6}` |
| `kg` | obj | KG store | `{"error": ..., "neighbors_2hop": []}` |
| `forecast` | obj | timemachine + bkt_forecaster | `{"error": ..., "curve": []}` |
| `attribution` | obj | mistakes._gather_user_records | `{"error": ..., "latest_mistakes": []}` |
| `cov` | obj | data/cov_demo_cases.json | `{"error": ..., "recent_claims": []}` |
| `debate` | obj | critic_agent.get_debate_logs | `{"error": ..., "recent_traces": []}` |
| `safety` | obj | A 的 pedagogical_safety | `{"error": ...}` |
| `ledger` | obj | A 的 claim_ledger | `{"error": ...}` |

**严格保证**：所有 key 必现；任一子块异常仍返回 200 + error 字段。

---

## 4. 演示资产健康检查清单（14/14）

```
verify_demo_assets:
 1. seed.json
 2. seed_extended.json
 3. question_bank.json (>=200 题)
 4. knowledge_base/ (>=20 章)
 5. cov_demo_cases.json (5 案例)
 6. variant_demo_samples.json (5 样例)
 7. RealDINA snapshots (5 demo)
 8. DiagnosisReporter × 5 demo users
 9. VariantGenerator × 5 demo samples
10. CoVDemoService × 5 axes
11. PedagogicalSafety × 5 cases (P1.1)
12. ClaimLedger × 5 source types (P1.2)
13. Cockpit 聚合端点 (8 blocks)
14. FastAPI routes registered
```

**冻结约定**：14 项任一失败即视为接口不稳定，禁止冻结。

---

## 5. 关键数据 schema 引用

| schema | 文档 | 行数 |
|--------|------|------|
| Cockpit 8 块 | [cockpit-endpoint.md](cockpit-endpoint.md) | 216 |
| LLM Client + PromptCache | [llm-client.md](llm-client.md) | 130 |
| 创新点 13 项对照 | [../10-学术与工程创新对照表.md](../10-学术与工程创新对照表.md) | 300+ |
| 5 大功能赛题对照 | [../08-赛题覆盖度审查与优化报告.md](../08-赛题覆盖度审查与优化报告.md) | 250+ |
| benchmark sakt full | [../benchmarks/sakt_benchmark.md](../benchmarks/sakt_benchmark.md) | 101 |
| benchmark sm2/fsrs/hlr | [../benchmarks/sm2_fsrs_hlr.md](../benchmarks/sm2_fsrs_hlr.md) | 200+ |

---

## 6. 冻结后变更规则（6/30 起执行）

### 6.1 允许的变更（无需双方同意）

- ✅ Bug fix（不改字段名 / 不改类型）
- ✅ 文档错别字修正
- ✅ 测试补充
- ✅ 性能优化（不影响响应 schema）
- ✅ 新增可选 query 参数（向后兼容）

### 6.2 必须双方同意 + issue 走流程

- ❌ 修改任一已发布字段的名字 / 类型 / 必选性
- ❌ 删除任一已发布路由
- ❌ 修改 HTTP method / status code
- ❌ 修改 Cockpit 任一子块的 keys 列表

### 6.3 流程模板

```markdown
# Issue: [冻结后变更] {简要描述}
**变更类型**: schema 变更 / 路由删除 / 其他
**影响范围**: 前端 CockpitView / Postman 演示 / docs/X
**理由**: 必须改 vs 想改
**回滚方案**: ...
**A 同意 [ ]   B 同意 [ ]**
```

---

## 7. 6/30 冻结仪式 checklist

- [ ] A 跑 `python -m scripts.verify_demo_assets` 14/14 通过
- [ ] B 跑 `pytest tests/b` 全绿
- [ ] A 跑 `pytest tests/a` 全绿
- [ ] A + B 各 review 本文档一遍，发现遗漏的接口立即补
- [ ] 把本文件改名为 `CONTRACT-FROZEN-2026-06-30.md` 并加 git tag `contract-freeze-v1`
- [ ] 更新 [docs/api/llm-client.md](llm-client.md) / [cockpit-endpoint.md](cockpit-endpoint.md) 顶部都标"冻结"
- [ ] 在 README 加一行"接口已于 2026-06-30 冻结，详见 docs/api/CONTRACT-FROZEN"

---

## 8. 字段歧义解决记录（2026-06-30 冻结前 A 全部消解）

| # | 项 | 决议 | 负责 | 状态 |
|---|---|------|-----|------|
| 1 | `Cockpit.kg.current_kp` | **双字段并存**：`current_kp` 为 str（顶部 header 短文本用）+ `current_kp_meta` 为 obj `{id,name,course}`（详细信息用）。前端按场景取，已在 `frontend/src/types/cockpit.ts` 双字段建模 | A | ✅ 6/30 已落地 |
| 2 | `Cockpit.profile.dimensions` 中 `learning_goal` vs `learning_goals` | **双字段并存**：前端 MyWorkspace 优先用 `learning_goals: string[]`，空时回退 `learning_goal.target`。已在 `MyWorkspace.vue:34-39` 实现 | A | ✅ 6/30 已落地 |
| 3 | `Cockpit.forecast.counterfactual` 字段 | **以 cockpit-endpoint.md §4.3 为准**：`{baseline_curve, recommended_curve, expected_gain, risk_warning}`。当前 5 demo user 全部返回 `{}` 空 dict（**P0 缺数据**）。B 需于 7/04 前在 seed 中补全；前端 ForecastCurve 已写 fallback | B | ⚠️ schema 冻结，数据待补 |
| 4 | `/cognitive/counterfactual` 与 `cockpit.forecast.counterfactual` 一致性 | **schema 完全一致**（相同 4 字段）。独立端点额外接受 `horizon_days` query 参数。前端 P1.4 反事实独立页用此端点，cockpit aggregator 用聚合 | A + B | ✅ 6/30 已落地 |
| 5 | `safety.evidence` 含正则字符串 | **前端不渲染原文**：MoreDrawer Safety Tab 只展示 `scaffolding_score / answer_leak_risk / misconception_reinforcement_risk / student_uptake_prompt` 4 个标量字段。`evidence` 仅保留在 API response 中供后端审计 | A | ✅ 6/30 已落地 |

> **新增遗留项**（详见 [开发日志/2026-06-29-A-给B的Phase1Day1实测清单.md](../../开发日志/2026-06-29-A-给B的Phase1Day1实测清单.md)）：
> - 🔴 P0：`profile.radar_labels` 返回 lone surrogate 乱码（前端已加 `safeRadarLabels` 兜底）—— **B 需修后端 UTF-8 编码**
> - 🔴 P0：`forecast.counterfactual = {}` 数据空 —— **B 7/04 前补**
> - 🟡 P1：`kg.neighbors_2hop / edges_2hop = []`、`attribution.total = 0`、`ledger.source_distribution` 全 0 —— **B 7/04 前补**
> - 🟢 P2：5 demo user 数据完全相同 —— **B W3 数据全量录制阶段解决**

---

## 9. 演示风险点（与字段无关，但与契约稳定性相关）

1. **CoV demo cases** 用 `data/cov_demo_cases.json` 硬编码，演示前最后再 review 一次案例选择
2. **Debate trace** 当前用 `critic_agent.get_debate_logs`，依赖运行时数据；演示前 seed 一组固定 trace
3. **Cockpit 5s+ 延迟**（含 forecast + KG 子图），评委演示时建议先 warm-up；或加 PromptCache + B 端做 warm cache
4. **离线模式 (A3_OFFLINE_DEMO=1)** 必须 README 显著位置写明

---

## 10. 签字栏

| 角色 | 同意冻结 | 日期 | 备注 |
|------|---------|------|------|
| A | [x] | 2026-06-30 | verify_demo_assets 14/14 通过；pytest tests/a 737 passed；§8 5 项歧义全部消解；前端 fixture + 乱码兜底已落库 |
| B | [ ] | YYYY-MM-DD | 待 B 上线签字；同时 7/04 前需补 P0/P1 数据项 |
| 用户 (产品决策) | [ ] | YYYY-MM-DD | |

---

> **维护**：本文档 6/30 前每日 review；冻结后任何变更必须经 §6.2 流程。
