# Profile Completeness Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make profile and cockpit completeness exclude normalized `unknown` placeholders and report the same percentage.

**Architecture:** Put the meaningful-dimension predicate and completeness calculation in `profile_schema.py`, alongside the six-dimension schema it evaluates. The profile endpoint and cockpit aggregator will both call that shared function; regression tests will lock the one-filled-dimension result at `(1, 6, 16.7)`.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy, pytest

---

## File Map

- Create `tests/b/test_profile_schema.py`: focused unit coverage for the shared calculation.
- Modify `backend/app/services/profile_schema.py`: authoritative meaningful-content predicate and completeness function.
- Modify `tests/b/test_persistence_api.py`: correct the obsolete one-dimension response expectations.
- Modify `backend/app/api/v1/profile.py`: replace its nested calculation with the shared helper.
- Modify `tests/b/test_cockpit_endpoint.py`: regression coverage for normalized unknown placeholders.
- Modify `backend/app/api/v1/cockpit.py`: use the same shared completeness helper.
- Create `开发日志/2026-07-10-profile完整度统计口径统一.md`: record cause, changes, and verification.

### Task 1: Shared Profile Completeness Calculation

**Files:**
- Create: `tests/b/test_profile_schema.py`
- Modify: `backend/app/services/profile_schema.py`

- [ ] **Step 1: Write the failing unit tests**

```python
from backend.app.services import profile_schema


def test_calculate_profile_completeness_excludes_unknown_placeholders():
    profile = profile_schema.normalize_profile({
        "knowledge_base": {"level": "middle", "score": 0.6},
    })

    assert profile_schema.calculate_profile_completeness(profile) == (1, 6, 16.7)


def test_dimension_meaningful_accepts_status_evidence_and_real_fields():
    meaningful = profile_schema.is_profile_dimension_meaningful

    assert meaningful({"status": "unknown", "evidence": []}) is False
    assert meaningful({"status": "ready", "evidence": []}) is True
    assert meaningful({"status": "unknown", "evidence": ["quiz-1"]}) is True
    assert meaningful({"score": 0.6}) is True
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b/test_profile_schema.py -q --tb=short --no-cov --benchmark-disable
```

Expected: FAIL because `calculate_profile_completeness` and `is_profile_dimension_meaningful` do not exist.

- [ ] **Step 3: Implement the shared functions**

Append to `backend/app/services/profile_schema.py`:

```python
def is_profile_dimension_meaningful(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        real_keys = {
            key for key in value if key not in ("status", "evidence", "_schema")
        }
        if real_keys:
            return True
        status = value.get("status", "")
        if status and status != "unknown":
            return True
        return bool(value.get("evidence", []))
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def calculate_profile_completeness(
    profile: dict[str, Any] | None,
) -> tuple[int, int, float]:
    values = profile or {}
    total = len(STANDARD_PROFILE_KEYS)
    filled = sum(
        1
        for key in STANDARD_PROFILE_KEYS
        if is_profile_dimension_meaningful(values.get(key))
    )
    return filled, total, round(filled / total * 100, 1)
```

- [ ] **Step 4: Run the unit tests and verify GREEN**

Run the command from Step 2.

Expected: `2 passed`.

### Task 2: Align the Profile API Contract Test and Implementation

**Files:**
- Modify: `tests/b/test_persistence_api.py:30-32`
- Modify: `backend/app/api/v1/profile.py:14-22,129-160`

- [ ] **Step 1: Confirm the obsolete assertion is RED**

Run:

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b/test_persistence_api.py::test_profile_api_uses_repository_and_preserves_response -q --tb=short --no-cov --benchmark-disable
```

Expected: FAIL with `assert 1 == 6`.

- [ ] **Step 2: Correct the one-dimension response expectations**

Replace the two obsolete assertions with:

```python
assert response["total_dimensions"] == 6
assert response["filled_dimensions"] == 1
assert response["completeness"] == 16.7
```

- [ ] **Step 3: Replace the local algorithm with the shared helper**

Import `calculate_profile_completeness` from `profile_schema`, remove the nested `_is_dimension_meaningful`, and calculate:

```python
filled, total, completeness = calculate_profile_completeness(profile)
```

Return `total` as `total_dimensions` and the already-rounded `completeness` value.

- [ ] **Step 4: Verify the profile API test is GREEN**

Run the command from Step 1.

Expected: `1 passed`.

### Task 3: Align Cockpit Completeness

**Files:**
- Modify: `tests/b/test_cockpit_endpoint.py`
- Modify: `backend/app/api/v1/cockpit.py:548-586`

- [ ] **Step 1: Write the failing cockpit regression test**

```python
def test_cockpit_completeness_excludes_unknown_placeholders(monkeypatch):
    from backend.app.api.v1 import cockpit
    from backend.app.services.profile_schema import normalize_profile

    profile = normalize_profile({
        "knowledge_base": {"level": "middle", "score": 0.6},
    })
    monkeypatch.setattr(cockpit, "_load_profile_record", lambda user_id: profile)

    assert cockpit._fetch_profile("u1")["completeness"] == 16.7
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b/test_cockpit_endpoint.py::test_cockpit_completeness_excludes_unknown_placeholders -q --tb=short --no-cov --benchmark-disable
```

Expected: FAIL because cockpit currently counts all six truthy placeholder dictionaries and returns `100.0`.

- [ ] **Step 3: Use the shared helper in cockpit**

Inside `_fetch_profile`, import `calculate_profile_completeness` with `PROFILE_DIMENSIONS`, then replace the truthiness-based calculation with:

```python
if PROFILE_DIMENSIONS:
    _, _, completeness = calculate_profile_completeness(profile)
else:
    completeness = 0.0
```

- [ ] **Step 4: Run the cockpit test and verify GREEN**

Run the command from Step 2.

Expected: `1 passed`.

### Task 4: Regression Verification and Development Log

**Files:**
- Create: `开发日志/2026-07-10-profile完整度统计口径统一.md`

- [ ] **Step 1: Run focused regression tests**

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b/test_profile_schema.py tests/b/test_persistence_api.py tests/b/test_cockpit_endpoint.py -q --tb=short --no-cov --benchmark-disable
```

Expected: all selected tests pass.

- [ ] **Step 2: Run all B tests**

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b -q --tb=short --no-cov --benchmark-disable
```

Expected: all `tests/b` tests pass.

- [ ] **Step 3: Run the full pytest suite**

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest -q --tb=short --no-cov --benchmark-disable
```

Expected: the profile persistence failure is gone; any remaining failures are limited to the previously identified question-bank data drift.

- [ ] **Step 4: Write the development log**

Create `开发日志/2026-07-10-profile完整度统计口径统一.md` containing:

```markdown
# 2026-07-10 Profile 完整度统计口径统一

## 问题

记录单维度更新被 profile API 统计为 16.7%，但旧测试仍期待 100%，且 cockpit 对同一份规范化画像仍会返回 100%。

## 根因

六维规范化会补入 `unknown` 占位字典；profile API 已排除占位维度，cockpit 与旧测试仍采用“键存在/字典非空即已填”的旧口径。

## 修复

- 在 `profile_schema.py` 提供统一的实质内容判断和完整度计算。
- profile API 与 cockpit 复用同一算法。
- 单维度更新统一返回 `filled_dimensions=1`、`total_dimensions=6`、`completeness=16.7`。
- 增加共享算法与跨接口回归测试。

## 验证

填写实际执行的测试命令和通过/失败数量；如全量仍存在题库数据漂移，逐项注明其与本次修复无关。
```

- [ ] **Step 5: Check only intended files changed**

Run:

```powershell
git status --short
git diff --check -- backend/app/services/profile_schema.py backend/app/api/v1/profile.py backend/app/api/v1/cockpit.py tests/b/test_profile_schema.py tests/b/test_persistence_api.py tests/b/test_cockpit_endpoint.py 开发日志/2026-07-10-profile完整度统计口径统一.md
```

Expected: no whitespace errors; unrelated pre-existing frontend files remain untouched.
