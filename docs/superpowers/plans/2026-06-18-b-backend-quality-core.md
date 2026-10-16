# B Backend Quality Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the offline-verifiable B backend reliable: all B tests green, algorithm state persistent, forecast and mistake-review APIs complete, and database/metrics operations reproducible.

**Architecture:** Preserve the existing FastAPI and SQLAlchemy structure while making repositories explicit dependencies of stateful algorithms. Pure algorithm services remain usable without a database; API and persistence adapters add validation, recovery, monitoring, and stable serialization.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, SQLAlchemy, SQLite, NumPy, pytest, Alembic-compatible migration scripts.

---

### Task 1: Repair the existing B regression suite

**Files:**
- Modify: `backend/app/services/cognitive_diagnosis/dina.py`
- Modify: `backend/app/services/cognitive_diagnosis/bkt.py`
- Modify: `backend/app/services/spaced_repetition/sm2.py`
- Modify: `backend/app/services/knowledge_graph/store.py`
- Modify: `backend/app/services/knowledge_graph/retriever.py`
- Modify: `backend/app/services/learner_archetype.py`
- Modify: `backend/app/services/learner_archetype_validation.py`
- Modify: `backend/app/services/cognitive_diagnosis/bkt_forecaster.py`
- Modify: `backend/app/agents/path_planner.py`
- Modify: `backend/app/api/v1/mistakes.py`
- Modify: `docs/API-CONTRACT.md`
- Test: existing files under `tests/b/`

- [ ] **Step 1: Re-run each failing test independently**

Run:

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest `
  tests/b/test_cognitive_diagnosis.py `
  tests/b/test_graph_rag_hybrid.py `
  tests/b/test_sm2_and_kg.py `
  tests/b/test_phase23_algorithms.py `
  tests/b/test_archetype_narrative_svg.py `
  tests/b/test_contract_document.py -q
```

Expected: failures reproduce the current DINA `Q` NameError, stale database session behavior, SM-2 due scheduling, archetype API mismatch, counterfactual monotonicity, and contract omissions.

- [ ] **Step 2: Fix DINA matrix flow**

Replace internal references to undefined `Q` with validated `q_matrix`; normalize it once to `np.ndarray`; reject shape mismatches; keep exact and mean-field paths on the same matrix.

- [ ] **Step 3: Fix BKT and SM-2 semantics**

Use an appropriate trend window for BKT. For a failed SM-2 review (`quality < 3`), set `next_review_at` to the current time so it appears in the immediate review queue.

- [ ] **Step 4: Fix database isolation in GraphRAG**

Make `KnowledgeGraphStore` resolve sessions from the current configured `SessionLocal`, and make BFS include both relation endpoints without relying on a stale global session factory.

- [ ] **Step 5: Stabilize archetype and planner interfaces**

Expose the 9-type mapping through `LearnerArchetypeService.ARCHETYPES`; repair validation callers; replace the invalid `Bloomberg` symbol with `BloomTaxonomy`; ensure real planner tests exercise `arm_pulls`.

- [ ] **Step 6: Fix forecast monotonicity and route ordering**

Ensure higher daily practice rates cannot reduce projected mastery. Register fixed mistake routes before dynamic `/{user_id}` routes.

- [ ] **Step 7: Verify Task 1**

Run:

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b -q
```

Expected: existing suite has zero failures before adding new requirements.

- [ ] **Step 8: Commit**

```powershell
git add backend/app tests/b docs/API-CONTRACT.md
git commit -m "fix: stabilize B algorithm regression suite"
```

### Task 2: Complete DINA/BKT/SM-2 persistence

**Files:**
- Modify: `backend/app/services/cognitive_diagnosis/state_repository.py`
- Modify: `backend/app/services/cognitive_diagnosis/dina.py`
- Modify: `backend/app/services/cognitive_diagnosis/bkt.py`
- Modify: `backend/app/services/spaced_repetition/sm2.py`
- Create: `tests/b/test_algorithm_state_persistence.py`

- [ ] **Step 1: Write failing persistence tests**

Tests must create a temporary SQLite engine, inject a `StateRepository`, save state through an algorithm instance, construct a new instance, restore, and assert equality for DINA, BKT, and SM-2.

- [ ] **Step 2: Run tests and verify RED**

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b/test_algorithm_state_persistence.py -q
```

Expected: fail because repositories are not injectable or restoration is incomplete.

- [ ] **Step 3: Implement repository injection and restoration**

Add optional repository parameters, explicit `persist`/`restore` methods, `load_all_sm2`, and DINA bulk save/load. Keep pure in-memory operation when repository is omitted.

- [ ] **Step 4: Verify GREEN**

Run the new persistence tests, then all `tests/b`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/cognitive_diagnosis backend/app/services/spaced_repetition tests/b/test_algorithm_state_persistence.py
git commit -m "feat: persist B algorithm state reliably"
```

### Task 3: Complete the learning time-machine API

**Files:**
- Modify: `backend/app/services/cognitive_diagnosis/bkt_forecaster.py`
- Create: `backend/app/services/cognitive_diagnosis/kalman_smoother.py`
- Modify: `backend/app/api/v1/cognitive.py`
- Create: `tests/b/test_forecast_api.py`

- [ ] **Step 1: Write failing tests**

Cover CI non-shrinkage over horizon, counterfactual monotonicity, Kalman output, reverse planning success, reverse planning unreachable targets, and API schemas.

- [ ] **Step 2: Verify RED**

Run `tests/b/test_forecast_api.py`; expected failure is missing reverse plan and incomplete schema.

- [ ] **Step 3: Implement pure services**

Move Kalman logic to `kalman_smoother.py`. Add bounded binary search for the minimum practice rate and translate it into daily question counts.

- [ ] **Step 4: Add Pydantic API models**

Add validated forecast and reverse-plan request/response models and `POST /api/v1/cognitive/reverse-plan`.

- [ ] **Step 5: Verify and commit**

Run focused tests and all `tests/b`, then commit as `feat: complete learning time machine backend`.

### Task 4: Complete intelligent mistake review

**Files:**
- Create: `backend/app/services/mistake_review.py`
- Modify: `backend/app/api/v1/mistakes.py`
- Create: `tests/b/test_mistake_review.py`

- [ ] **Step 1: Write failing service and API tests**

Cover eight categories, attribution source, three or more Bloom variants with answer/explanation, automatic SM-2 enqueue, heatmap matrix, fixed route matching, and missing-record errors.

- [ ] **Step 2: Verify RED**

Run the new file; expect failures because current variants are text-only templates and recording does not enqueue SM-2.

- [ ] **Step 3: Implement service**

Build a rule attribution channel with an optional callable LLM channel. Return `source="llm"` or `source="rule_fallback"`. Generate structured variants.

- [ ] **Step 4: Refactor API**

Use Pydantic models, correct HTTP status codes, explicit error codes, and service calls. Do not add silent exception handlers.

- [ ] **Step 5: Verify and commit**

Run focused and full B tests, then commit as `feat: complete intelligent mistake review`.

### Task 5: Add database migrations, indexes, backup, and metrics

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/20260618_0001_b_backend_baseline.py`
- Modify: `backend/app/core/models.py`
- Create: `backend/app/core/metrics.py`
- Modify: `backend/app/main.py`
- Create: `scripts/backup_database.py`
- Create: `scripts/restore_database.py`
- Create: `tests/b/test_operations_infrastructure.py`

- [ ] **Step 1: Write failing operations tests**

Test required indexes in SQLAlchemy metadata, metrics text format, SQLite backup/restore round trip, and migration file presence/revision shape.

- [ ] **Step 2: Verify RED**

Run the new operations test file; expected failures are absent indexes, metrics registry, and scripts.

- [ ] **Step 3: Add indexes and baseline migration**

Add composite indexes for high-frequency user/KP and due-date queries. Create a baseline migration matching current metadata.

- [ ] **Step 4: Add backup/restore**

Use `sqlite3.Connection.backup`; verify source and backup with `PRAGMA integrity_check`; refuse an invalid restore source.

- [ ] **Step 5: Add Prometheus text metrics**

Implement counters and latency summaries without a mandatory third-party package. Expose `GET /metrics` with Prometheus content type.

- [ ] **Step 6: Verify and commit**

Run focused tests, all B tests, and compileall; commit as `feat: add B backend operations foundation`.

### Task 6: Final verification and development log

**Files:**
- Modify: `开发日志/B2026-6-18.md`

- [ ] **Step 1: Run the full verification**

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b -q
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m compileall -q backend/app scripts
```

- [ ] **Step 2: Run performance checks**

Run the B benchmark tests and a direct DINA 100×50 benchmark. Record measured values, not target values.

- [ ] **Step 3: Update the development log**

Append the actual root causes, files changed, test counts, benchmark outputs, migrations/metrics usage, and deferred external-data work.

- [ ] **Step 4: Commit**

```powershell
git add 开发日志/B2026-6-18.md
git commit -m "docs: record B backend quality core completion"
```
