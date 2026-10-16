# API-CONTRACT.md — A / B Shared Contract

> Freeze date: 2026-06-19 09:30
> Changes require both signatures + group notification
> **Breaking this contract = `git revert`**

## Contract 1: AgentResponse.metadata fields

| Field | Type | Writer | Reader | Notes |
|------|------|--------|--------|-------|
| `bloom_level` | str | A's QuizGenerator | B's DINA/Bloom | `remember/understand/apply/analyze/evaluate/create` |
| `kp_ids` | list[str] | All A's Agents | B's DINA/BKT/SM-2 | Knowledge point IDs |
| `archetype_code` | str | B's ProfileAgent | A's TutorAgent | 9 codes: `high_achiever`, `effort_chaser`, `rhythm_broken`, `habit_breakdown`, `introverted_explorer`, `social_learner`, `stable_average`, `exam_oriented`, `concept_explorer` |
| `zpd_kps` | list[str] | B's PathPlanner | A's CourseExpert | ZPD knowledge points |
| `reflection_trace` | list[dict] | A's all Agents | log only | `[{turn, issue, action}]` |
| `dina_snapshot` | dict | B's cognitive | A's Tutor | `{kp_id: mastery}` |
| `narrative_summary` | dict | B's NarrativeGenerator | A's ChatView | assessment narrative |
| `svg_assets` | dict | B's SVGVisualizer | A's artifacts | `{radar_svg, trend_svg, heatmap_svg}` |

## Contract 2: AgentContext.extra fields

| Field | Type | Writer | Reader | Notes |
|------|------|--------|--------|-------|
| `strategy_prompt` | str | Orchestrator (B's realtime) | All Agents | Real-time strategy |
| `dina_snapshot` | dict | B's chat hook | Personalized Agents | mastery snapshot |
| `archetype` | dict | B's ProfileAgent hook | A's TutorAgent | Full archetype object |
| `rag_mode` | str | A's chat.py | B's RagService | "tfidf"/"graph"/"hybrid" |
| `role_view` | str | A's chat.py | Orchestrator | "student"/"assistant"/"teacher" |

## Contract 3: Orchestrator `process_turn` signature (FROZEN until 6-25 21:00)

`AgentOrchestrator.process_turn()` **禁止修改参数签名**。

```python
async def process_turn(self, user_input: str, profile: dict, context: dict, conversation_history=None, rag_results=None, course_name: str = "artificial_intelligence", session_id: str = "") -> Dict[str, AgentResponse]
```

> ⚠️ **禁止修改参数签名** —— 任何字段名/类型变更必须双签 + 走 git revert 流程。

冻结字段：所有 chat 链路上的服务（含 `learning_state_store`）必须保持向后兼容。

## Contract 3b: 共享服务接口冻结

下列服务对象签名 FROZEN，B/A 任意一方不得单方面变更：

- `learning_state_store` — A/B 双写, 调用方传 user_id + state dict, 返回布尔
- `state_repository` (`get_state_repo`) — DINA/BKT/SM-2 持久化统一入口

## Contract 4: DB 17 张表所有权 (DB Tables: A5 + B12 = 17 total)

以下为 **DB 17 张表所有权** 冻结清单：

| Table | Owner | Other's access |
|------|-------|----------------|
| `resources`, `chat_sessions`, `debate_logs`, `agent_traces`, `artifacts` | A | B read-only via Service |
| `profiles`, `realtime_states`, `learning_paths`, `assessments`, `mistakes` | B | A via Service interface |
| `knowledge_points`, `kp_relations`, `learner_archetypes` | B | A via `lookup_kp()` |
| `dina_states`, `bkt_states`, `sm2_schedule`, `gamification_profiles` | B | A via `dina_snapshot` |

### Learner archetype codes

- `high_achiever`
- `effort_chaser`
- `rhythm_broken`
- `habit_breakdown`
- `introverted_explorer`
- `social_learner`
- `stable_average`
- `exam_oriented`
- `concept_explorer`

## Contract 5: Knowledge Base Split
- `knowledge_base/artificial_intelligence/` → A
- `knowledge_base/python_programming/` → B

## Contract 6: API Route Split (frozen, 不允许跨域)

- A: `/api/v1/chat/*`, `/api/v1/resources/*`, `/api/v1/artifacts/*`, `/api/v1/system/*`
- B:
  - `/api/v1/profile/*`
  - `/api/v1/learning-path/*`
  - `/api/v1/assessment/*`
  - `/api/v1/mistakes/*`
  - `/api/v1/cognitive/*`
  - `/api/v1/knowledge-graph/*`
  - `/api/v1/gamification/*`

Cross-domain persistence calls use `learning_state_store`.

> Signed: Developer A _____ Developer B _____
> Date: 2026-06-19
