# Phase 6 Release Decision (Scheduling-Only)

**Date**: 2026-03-02  
**Decision Scope**: 发布前调度门禁产品化结论（不包含真实远程 APK E2E）

## Inputs

- `bash scripts/ci_gate_entry.sh`
- `PYTHONPATH=. ./venv/bin/python scripts/daily_gate_healthcheck.py`
- `PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3`
- `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`

## Decision

- Latest gate status: `continue`
- Latest rollback readiness: `rollback_ready=True`
- Decision: **GO (for scheduling gate rollout governance only)**

## Preconditions

1. `core/config.py` default `TASK_BACKEND="dramatiq"` unchanged.
2. Runtime enqueue path uses `workers.task_actor` actor send.
3. Runtime switching remains env-var based only.

## Rollback Conditions

- Any gate output `hold` or `rollback_now`.
- `rollback_smoke` reports `rollback_ready=False`.
