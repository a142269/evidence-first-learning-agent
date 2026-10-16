# B Day 1 Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the B-owned in-memory profile, learning-path, and assessment stores with restart-safe SQLite repositories while preserving existing API response shapes and providing idempotent demo seed data.

**Architecture:** Add focused SQLAlchemy models in the shared database layer, then expose B-owned repositories that accept an injectable `session_factory`. API modules call repositories instead of dictionaries. A narrow compatibility service lets the existing Chat API persist profile/path/assessment output without importing API internals.

**Tech Stack:** Python 3.10+, SQLAlchemy 2.x, FastAPI, SQLite, pytest, FastAPI TestClient.

---

### Task 1: Freeze Cross-Domain Contracts

**Files:**
- Create: `docs/API-CONTRACT.md`
- Test: `tests/b/test_contract_document.py`

- [ ] Write a failing test that requires the contract document and verifies the frozen metadata, context, orchestrator signature, service import paths, and database ownership sections.
- [ ] Run `D:\Anaconda3\envs\dxtorch\python.exe -m pytest tests/b/test_contract_document.py -v` and confirm failure because the document is absent.
- [ ] Create `docs/API-CONTRACT.md` with exact field names and ownership boundaries from the approved design.
- [ ] Re-run the test and confirm it passes.

### Task 2: Add SQLAlchemy Models and Database Initialization

**Files:**
- Create: `backend/app/core/models.py`
- Modify: `backend/app/core/database.py`
- Modify: `backend/app/main.py`
- Test: `tests/b/test_database_models.py`

- [ ] Write failing tests using a temporary SQLite engine that require all B-owned tables and validate JSON payload round-tripping.
- [ ] Run the focused test and confirm failure because `backend.app.core.models` does not exist.
- [ ] Define `ProfileRecord`, `RealtimeStateRecord`, `LearnerArchetypeRecord`, `KnowledgePointRecord`, `KnowledgeRelationRecord`, `DinaStateRecord`, `BktStateRecord`, `Sm2ScheduleRecord`, `LearningPathRecord`, `AssessmentRecord`, `MistakeRecord`, and `GamificationProfileRecord`.
- [ ] Add `configure_database(database_url)` for tests and `init_db()` model import registration.
- [ ] Initialize tables during FastAPI startup before RAG warmup.
- [ ] Re-run focused tests and compile the backend.

### Task 3: Implement B Repositories

**Files:**
- Create: `backend/app/repositories/profile_repository_v2.py`
- Create: `backend/app/repositories/learning_path_repository.py`
- Create: `backend/app/repositories/assessment_repository.py`
- Test: `tests/b/test_persistence_repositories.py`

- [ ] Write failing repository tests for deep profile merge, reset, path ordering/progress, assessment summaries, and persistence across new sessions.
- [ ] Run tests and confirm imports fail.
- [ ] Implement repositories with transaction rollback, JSON-safe copies, deterministic ordering, and injectable session factories.
- [ ] Re-run tests and confirm all repository behaviors pass.

### Task 4: Migrate Profile, Path, and Assessment APIs

**Files:**
- Modify: `backend/app/api/v1/profile.py`
- Modify: `backend/app/api/v1/learning_path.py`
- Modify: `backend/app/api/v1/assessment.py`
- Test: `tests/b/test_persistence_api.py`

- [ ] Write failing TestClient tests against a temporary SQLite database while preserving current URL and response contracts.
- [ ] Run tests and confirm API data does not survive repository recreation.
- [ ] Replace module dictionaries with repository calls.
- [ ] Preserve dimension filtering, completeness calculations, generated IDs, progress semantics, assessment summary fields, and not-found payloads.
- [ ] Re-run API tests.

### Task 5: Add Chat Compatibility Service

**Files:**
- Create: `backend/app/services/learning_state_store.py`
- Modify: `backend/app/api/v1/chat.py`
- Test: `tests/b/test_learning_state_store.py`

- [ ] Write failing service tests for profile upsert, generated path persistence, and evaluation persistence.
- [ ] Run tests and confirm the service is missing.
- [ ] Implement service functions backed by B repositories.
- [ ] Replace Chat API imports of private `_profiles`, `_paths`, and `_assessments` dictionaries with these functions without changing the Chat API response contract.
- [ ] Re-run service and API tests.

### Task 6: Add Idempotent Demo Seed

**Files:**
- Create: `data/seed.json`
- Create: `scripts/seed_demo.py`
- Test: `tests/b/test_seed_demo.py`

- [ ] Write a failing test that imports seed data twice and expects stable row counts and complete demo profiles, paths, and assessments.
- [ ] Run it and confirm failure because the seed importer is absent.
- [ ] Add three demo learners with eight profile dimensions, one path, and two assessment records each.
- [ ] Implement `seed_database(seed_path, session_factory)` using repository upserts and deterministic IDs.
- [ ] Re-run the seed test twice.

### Task 7: Verify and Document Day 1

**Files:**
- Modify: `开发日志/B2026-6-18.md`

- [ ] Run `D:\Anaconda3\envs\dxtorch\python.exe -m pytest tests/b -v`.
- [ ] Run `D:\Anaconda3\envs\dxtorch\python.exe -m compileall -q backend scripts`.
- [ ] Run `git diff --check`.
- [ ] Record exact test counts, shared-file changes, database decisions, and remaining Day 2 work in the B log.
- [ ] Commit the completed Day 1 increment.
