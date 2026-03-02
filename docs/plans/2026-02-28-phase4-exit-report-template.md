# Phase 4 Exit Report Template (Scheduling-First)

## 1. Context
- Window range:
- Validation mode: `scheduling`
- Runtime routing: env-based only (`TASK_BACKEND`)
- Default config check: `core/config.py` keeps `TASK_BACKEND=dramatiq`

## 2. Snapshot Inputs
- Snapshot path(s):
- Command(s):
  - `scripts/scheduling_window_snapshot.py ...`
  - `scripts/canary_rollout_smoke.py --validation-mode scheduling ...`
  - `scripts/rollout_guard.py --validation-mode scheduling ...`

## 3. Scheduling Evidence Summary
| window | backend | can_enqueue | rollback_ready | success_rate | stuck_tasks | retry_recovered_rate | p95_queue_to_start_seconds | guard_action | guard_reason |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
|  |  |  |  |  |  |  |  |  |  |

## 4. Gate Decision
- GO/NO-GO:
- Primary reason:
- Triggered rollback: yes/no

## 5. Rollback Verification
- Command:
- Result:
- Evidence:

## 6. Residual Risks (Top 3)
1.
2.
3.

## 7. Notes
- 真实远程 APK 验证属于专项 E2E，不是每轮调度门禁。
