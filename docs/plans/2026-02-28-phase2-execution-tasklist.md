# Phase 2 Execution Tasklist (Agent Dispatch)

**Purpose:** This is the handoff checklist for another agent to execute Phase 2 end-to-end.  
**Baseline:** Phase 1.5 already closed. `TASK_BACKEND=dramatiq` must remain default.

## Dispatch Constraints
- Do not change [core/config.py](/Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统/core/config.py#L53) default `TASK_BACKEND`.
- Use TDD for each task: write failing test, then minimal fix, then verify.
- Keep each task in an isolated commit.
- Do not remove Dramatiq worker path in Phase 2.

## Task A: Stage Service Extraction
**Work**
- Create `modules/task_orchestration/stage_services.py`
- Refactor `workers/static_analyzer.py`, `workers/dynamic_analyzer.py`, `workers/report_generator.py` into thin wrappers.
- Add `tests/test_stage_services.py`

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q tests/test_stage_services.py
```

**Done When**
- Stage logic can run without Dramatiq decorator context.

## Task B: State Machine Core
**Work**
- Create `modules/task_orchestration/state_machine.py`
- Add transition and retry policy functions.
- Add `tests/test_state_machine.py`

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q tests/test_state_machine.py
```

**Done When**
- Transition table is deterministic and test-covered.

## Task C: Dramatiq Actor Runtime
**Work**
- Implement state-machine execution in `workers/task_actor.py`.
- Use DB status to decide next stage and re-enqueue behavior.
- Add `tests/test_task_actor_state_machine_runtime.py`.

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q tests/test_task_actor_state_machine_runtime.py
```

**Done When**
- `run_task(task_id)` 可推进一个阶段并正确持久化状态。

## Task D: Redis Lock + Backoff
**Work**
- Add per-task lock in `workers/task_actor.py`: `lock:task:{task_id}`.
- Add lock/backoff settings in `core/config.py` (new fields only).
- Add `tests/test_task_actor_retry_lock.py`.

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q tests/test_task_actor_retry_lock.py
```

**Done When**
- Duplicate actor execution is suppressed.
- Retry delay is controlled by config.

## Task E: API Queue Abstraction Adoption
**Work**
- Replace direct `enqueue_analysis_workflow(...)` calls in:
  - `api/routers/apk.py`
  - `api/routers/tasks.py`
- Route through `modules/task_orchestration/queue_backend.enqueue_task`.
- Update tests:
  - `tests/test_apk_router.py`
  - `tests/test_tasks_router.py`

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_apk_router.py \
  tests/test_tasks_router.py \
  tests/test_queue_backend.py \
  tests/test_queue_backend_dramatiq_path.py
```

**Done When**
- API behavior unchanged from client perspective.
- Backend switch works only through `TASK_BACKEND`.

## Task F: Integration Gate + Documentation
**Work**
- Update:
  - `docs/TESTING_GUIDE.md`
  - `docs/TEST_QUICK_REFERENCE.md`
- Create:
  - `docs/plans/2026-02-28-dramatiq-cutover-checklist.md`

**Verify**
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_stage_services.py \
  tests/test_state_machine.py \
  tests/test_task_actor_state_machine_runtime.py \
  tests/test_task_actor_retry_lock.py \
  tests/test_apk_router.py \
  tests/test_tasks_router.py \
  tests/test_queue_backend.py \
  tests/test_queue_backend_dramatiq_path.py

PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
```

**Done When**
- All verification commands pass.
- Cutover checklist includes explicit rollback path to Dramatiq.
