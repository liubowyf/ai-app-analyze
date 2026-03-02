# Phase 6 Baseline Freeze (Auditable)

**Date**: 2026-03-02  
**Mode**: Scheduling-only (no remote APK E2E in daily gate)  
**Freeze Scope**: Gate behavior, scripts contract, baseline test collect count, ops handling matrix

## 1. Gate Command Baseline and Latest Pass Evidence

Latest verified window (UTC): `2026-03-02T05:53:22Z ~ 2026-03-02T05:53:45Z`

1. `bash scripts/ci_gate_entry.sh`
- Expected: non-zero blocks pipeline; output must contain `final_action` and `final_reason`.
- Latest result: `final_action=continue`, `final_reason=all_gates_passed`, exit `0`.

2. `PYTHONPATH=. ./venv/bin/python scripts/daily_gate_healthcheck.py`
- Expected: `status=healthy` and phase5 3-run stability all continue.
- Latest result: `status=healthy`, `final_action=continue`, `final_reason=all_runs_continue`, exit `0`.

3. `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`
- Expected: runtime readiness true under Dramatiq-only path.
- Latest result: `backend=dramatiq`, `default_backend_is_dramatiq=True`, `actor_path_available=True`, `rollback_ready=True`.

## 2. Gate Script Inventory and Purpose

- `scripts/ci_gate_entry.sh`
  - Unified local/CI entrypoint.
  - Enforces output contract (`final_action`, `final_reason`) and propagates non-zero exit.

- `scripts/phase4_gate_check.py`
  - Single-run gate orchestrator.
  - Executes collect stability, collect-only, scheduling snapshot, rollout_guard, rollback_smoke.
  - Emits final decision (`continue|hold|rollback_now`).

- `scripts/phase5_stability_check.py`
  - Runs phase4 gate repeatedly (`--runs`, default 3).
  - Any non-continue run fails the full check.

- `scripts/daily_gate_healthcheck.py`
  - Daily scheduled health probe.
  - Wraps phase5 stability check and emits structured alert payload on failure.

## 3. Test Collection Baseline

- Baseline collect count: **358 tests collected**
- Current collect count after adding baseline-freeze regression tests: **361 tests collected**
- Evidence commands:
  - `PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py`
  - `PYTHONPATH=. ./venv/bin/pytest --collect-only -q`
- Last refreshed at: **2026-03-02T05:53:xxZ**

## 4. Known Risks and Mitigations

1. Risk: sample window drift can move gate from `continue` to `hold`.
- Mitigation: run `scripts/generate_scheduling_samples.py --count 30` before re-evaluating gate.

2. Risk: output contract regressions (`final_action/final_reason` missing) can silently break CI parsing.
- Mitigation: keep `tests/test_ci_gate_entry_integration.py` and baseline audit script in mandatory test set.

3. Risk: scheduling-only evidence does not prove remote analysis quality.
- Mitigation: keep remote APK E2E as separate专项验证 before major rollout milestones.

## 5. Constraints Check (Freeze Guardrails)

- `core/config.py` default is `TASK_BACKEND = "dramatiq"`.
- Runtime enqueue path is actor-based (`workers.task_actor.run_task.send`).
- Runtime canary switching remains env-driven only; no hardcoded traffic switch.
