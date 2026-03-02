# Dramatiq Redis-MySQL Migration Implementation Plan

**Last Updated:** 2026-03-02  
**Status:** Migration completed (Dramatiq-only baseline active)

## 1. Objective
- Complete migration from Dramatiq chain orchestration to Dramatiq actor orchestration.
- Keep MySQL as source of truth for state.
- Run scheduling gates on a Dramatiq-only runtime baseline.

## 2. Hard Constraints
- Keep code default `TASK_BACKEND=dramatiq` in `core/config.py`.
- Runtime enqueue path must be actor-based (`workers.task_actor`).
- Runtime traffic switching is env-based only.
- During normal dev/test iterations, use scheduling-only validation:
  - Do not require real remote APK full analysis runs as per-change gate.
  - Validate by queue/actor/state-machine tests and smoke scripts (`canary_rollout_smoke.py`, `rollback_smoke.py`, collect stability).
  - Run real remote APK analysis only in dedicated E2E checkpoints.

## 3. Milestone Record

### Phase 1 / 1.5 / 2 / 2.1 / 2.2
- Completed.
- Queue abstraction, actor runtime, stability gates, diagnostics and smoke scripts are in place.

### Phase 2.3-R2
- Completed.
- Fixed proxy-port false availability detection and actor retry status restoration.
- Added dynamic evidence quality and canary evidence gates.

### Phase 2.4 (Canary Validation)
- Marked **PASS (GO)** by decision.
- Result basis: 3-sample Dramatiq canary all passed evidence gates (`runs/network/domains/img > 0`).
- Note: sample size is explicitly limited and was strengthened by later scheduling gates.

## 4. Current Baseline
- Backend diagnostics endpoint is available: `GET /api/v1/tasks/metrics/backend`.
- Canary/rollback scripts are available:
  - `scripts/canary_rollout_smoke.py`
  - `scripts/rollback_smoke.py`
- Collect stability gate remains mandatory:
  - `scripts/verify_collect_stability.py`

## 5. Phase 3 Result
- Marked **PASS (GO)** by decision after rollout hardening execution.
- Gate evidence and rollback drill are available in:
  - `docs/plans/2026-02-28-phase3-exit-report.md`
- Decision note:
  - Current approval is based on 3-sample window.
  - Larger sample / longer window is recorded as follow-up improvement, not blocking.

## 6. Phase 4+ Scope
- Continue controlled expansion with stronger statistical confidence.
- Keep scheduling gate automation and auditability as default governance baseline.
- Execute dedicated remote APK E2E only at explicit milestone checkpoints.

Execution handoff:
- `docs/plans/2026-02-28-phase4-expansion-tasklist.md`
