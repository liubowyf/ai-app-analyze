# Dramatiq Cutover Checklist (2026-02-28)

## Scope
- Keep `TASK_BACKEND=dramatiq` as current default baseline.
- Cutover to Dramatiq is controlled only by environment switch.

## Pre-Cutover Checks
- Verify Dramatiq worker task registration (no `-I` flags required):
  - `PYTHONPATH=. ./venv/bin/python -c "from workers.task_actor import `task_actor`; `task_actor`.loader.import_default_modules(); print([name for name in `task_actor`.tasks if name.startswith('workers.')])"`
  - expected task prefixes:
    - `workers.static_analyzer.*`
    - `workers.dynamic_analyzer.*`
    - `workers.report_generator.*`
- Verify queue-backend tests are green:
  - `PYTHONPATH=. ./venv/bin/pytest -q tests/test_queue_backend.py tests/test_queue_backend_dramatiq_path.py tests/test_queue_backend_runtime_status.py`
- Verify actor runtime tests are green:
  - `PYTHONPATH=. ./venv/bin/pytest -q tests/test_task_actor_state_machine_runtime.py tests/test_task_actor_retry_lock.py tests/test_task_actor_observability.py`
- Verify collection stability:
  - `PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py`

## Phase 2.2 Canary Evidence (Required)
- Runtime diagnostics endpoint evidence (`GET /api/v1/tasks/metrics/backend`):
  - `backend`
  - `dramatiq_ready`
  - `can_enqueue`
  - `timestamp`
- Canary smoke script evidence:
  - `PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py`
  - required fields: `backend`, `dramatiq_ready`, `fallback_reason`, `can_enqueue`, `actor_path_available`, `go_no_go`
- Rollback smoke script evidence:
  - `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`
  - required fields: `backend`, `default_backend_is_dramatiq`, `actor_path_available`, `rollback_ready`

## Cutover Steps (Controlled)
1. Deploy code with Dramatiq default unchanged.
2. Ensure Dramatiq worker process is up and healthy.
3. Set runtime env: `TASK_BACKEND=dramatiq` for selected scope.
4. Submit canary tasks and confirm stage progression (`queued -> static -> dynamic -> report -> completed`).
5. Monitor enqueue failure logs and retry/lock behavior.

## Post-Cutover Validation
- API enqueue path sanity:
  - `PYTHONPATH=. ./venv/bin/pytest -q tests/test_apk_router.py tests/test_tasks_router.py`
- Full collect sanity:
  - `PYTHONPATH=. ./venv/bin/pytest --collect-only -q`

## Rollback (Explicit Dramatiq Path)
1. Reset env immediately: `TASK_BACKEND=dramatiq`.
2. Restart API processes to load updated env.
3. Keep Dramatiq workers running (do not remove Dramatiq path).
4. Re-run smoke checks:
   - `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`
   - `PYTHONPATH=. ./venv/bin/pytest -q tests/test_queue_backend.py tests/test_apk_router.py tests/test_tasks_router.py`
5. Confirm new tasks are back on Dramatiq workflow.

## Notes
- Do not change `core/config.py` default `TASK_BACKEND` during cutover operations.
- Dramatiq unavailability must fail enqueue with explicit `False` (no fake success).

## Phase 3 Hardening Addendum

### Rollout Guard
- Use runtime snapshot to decide continue vs rollback:
  - `PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/rollout_window.json`
- Trigger rollback immediately when any condition is true:
  - failure rate `> 5%`
  - any zero-evidence task (`runs/network/domains/img` contains `0`)
  - backend `can_enqueue=false`

### Structured Canary Summary
- `scripts/canary_rollout_smoke.py` output must include:
  - `success_rate`
  - `p95_duration_seconds`
  - `evidence_completeness_rate`
  - `failed_reason_topN`

### Incident Handoff Minimum Fields
- `window_id`, `time_range`, `backend_group`
- `trigger_reason`, `affected_task_ids`
- `rollback_completed_at`, `next_owner`
