# B Remaining Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining B-owned items from the 2026-06-23 A/B follow-up plan so they are backed by code, evidence, and verification.

**Architecture:** Finish the remaining work in four slices: Bloom 6x3 relabel artifacts, RAG-Fusion reranking, B-side strict typing on five selected modules, and a tests/b coverage baseline report. Each slice should add or update a small number of files and be validated independently before moving on.

**Tech Stack:** Python 3.10, FastAPI services, pytest, mypy, Ruff, JSON data assets, Markdown reports.

---

### Task 1: Bloom 6x3 Relabel Artifacts

**Files:**
- Create: `scripts/relabel_bloom_6x3.py`
- Create: `reports/bloom_6x3_relabel_20260623.md`
- Modify: `data/question_bank.json`
- Test: `tests/b/test_bloom_6x3.py`

- [ ] Add a failing test that asserts a relabel helper can annotate question-bank items with Bloom 6x3 detail fields and emit a summary.
- [ ] Run the test alone and verify it fails because the helper does not exist yet.
- [ ] Implement the minimal relabel script/helper that loads the question bank, classifies each item via `Bloom6x3Config`, writes back stable detail fields, and returns a summary dict.
- [ ] Run the targeted Bloom tests and verify they pass.
- [ ] Generate a markdown relabel report with counts, field examples, and a short human spot-check summary.

### Task 2: RAG-Fusion Reranking

**Files:**
- Modify: `backend/app/services/knowledge_graph/retriever.py`
- Modify: `tests/b/test_graph_rag_hybrid.py`
- Create: `reports/rag_fusion_examples_20260623.md`

- [ ] Add a failing test that asserts the retriever supports a dedicated RAG-Fusion mode and returns ranked examples with fusion scores.
- [ ] Run the targeted GraphRAG test and verify it fails for the expected missing behavior.
- [ ] Implement the minimal reciprocal-rank fusion path in `GraphRetriever.retrieve(...)`, preserving existing hybrid behavior.
- [ ] Run the targeted GraphRAG tests and verify they pass.
- [ ] Write a short report with at least three query examples showing ranking changes.

### Task 3: B-Side Mypy Strict Set

**Files:**
- Modify: `mypy.ini`
- Modify: selected B-owned modules based on the first strict run
- Create: `开发日志/B2026-6-23-B-mypy-strict-5模块.md`

- [ ] Pick five B-owned modules with clear ownership and moderate scope.
- [ ] Run mypy on those exact modules under strict mode and capture the initial failures.
- [ ] Fix the reported type issues with minimal behavior changes.
- [ ] Re-run mypy on the exact five modules and verify zero errors.
- [ ] Record the chosen module list and command results in a B dev log.

### Task 4: tests/b Coverage Baseline

**Files:**
- Create: `reports/tests_b_coverage_baseline_20260623.md`

- [ ] Run a coverage-capable tests/b command in the current Windows environment with a repo-local temp directory.
- [ ] If coverage succeeds, capture the baseline percentage and the command used.
- [ ] If environment issues still block a clean exit, capture the exact blocker, the partial evidence, and a recommended CI/Linux-first interpretation.
- [ ] Write the baseline report with command, environment note, and next-step recommendation.
