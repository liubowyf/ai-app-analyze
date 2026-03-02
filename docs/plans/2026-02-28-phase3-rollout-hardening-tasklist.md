# Phase 3 Rollout Hardening Tasklist (Agent Dispatch)

**Purpose:** expand real traffic safely and lock operational confidence after Phase 2.4.  
**Baseline:** Phase 2.4 marked GO with 3 canary samples.

## Global Constraints
- Keep `core/config.py` default `TASK_BACKEND=dramatiq`.
- Do not remove Dramatiq path or Dramatiq workers.
- Rollout by env/runtime switch only.

## Task A: 10% Traffic Window Validation
**Work**
- Run Dramatiq for 10% target traffic over at least one fixed window (recommended 2-4 hours).
- Keep Dramatiq as fallback pool simultaneously.
- Collect per-task evidence metrics (`runs/network/domains/report_img`).

**Pass Gate**
- Success rate >= 95%.
- No task with zero evidence (`runs/network/domains/img` must all be > 0).
- If gate breaks once: mark window failed and rollback immediately.

## Task B: Rollback Trigger and Drill Automation
**Work**
- Add one wrapper script: `scripts/rollout_guard.py`.
- Input: rolling stats snapshot.
- Output: `continue` or `rollback_now` with reason.
- Include explicit trigger rules:
  - failure rate > 5%
  - any zero-evidence task
  - backend can_enqueue false

**Pass Gate**
- Script returns deterministic action and reason.
- Tests cover each rollback trigger branch.

## Task C: Observability Tightening
**Work**
- Add structured rollout summary output to canary pipeline:
  - success_rate
  - p95_duration
  - evidence completeness rate
  - failed_reason_topN
- Ensure task_actor and queue diagnostics logs include stable keys for parsing.

**Pass Gate**
- Summary can be produced from one run without manual parsing.
- Tests validate summary field presence.

## Task D: Operations Playbook Finalization
**Work**
- Update:
  - `docs/OPERATIONS.md`
  - `docs/TESTING_GUIDE.md`
  - `docs/TEST_QUICK_REFERENCE.md`
  - `docs/plans/2026-02-28-dramatiq-cutover-checklist.md`
- Add Phase 3 runbook section:
  - rollout commands
  - rollback triggers
  - evidence checklist
  - incident handoff template

**Pass Gate**
- All commands in docs are runnable as written.
- Rollback section is complete and explicit.

## Task E: Phase 3 Exit Report
**Work**
- Produce one report artifact:
  - `docs/plans/2026-02-28-phase3-exit-report.md`
- Include:
  - observed windows
  - gate outcomes
  - rollback drills
  - open risks
  - GO/NO-GO recommendation for next phase

**Pass Gate**
- Report is evidence-based and references concrete task/window data.

## Mandatory Verification Commands
```bash
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py --runs-count 1 --network-count 1 --domains-count 1 --report-img-count 1
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```
