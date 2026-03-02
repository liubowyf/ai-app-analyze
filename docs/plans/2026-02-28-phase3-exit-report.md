# Phase 3 Exit Report (2026-02-28)

## Scope
- Plan: `docs/plans/2026-02-28-phase3-rollout-hardening-tasklist.md`
- Constraint check: default `TASK_BACKEND=dramatiq` unchanged; Dramatiq path retained.

## Observed Window
- `window_id`: `phase3-2026-02-28-window-01`
- backend: `dramatiq` (runtime window snapshot)
- samples: 3 tasks

| task_id | status | duration_seconds | runs | network | domains | img_count | report_url |
|---|---:|---:|---:|---:|---:|---:|---|
| 7c7d9c3f-b09f-4df0-88d9-c9704bb877e7 | completed | 771 | 3 | 16 | 5 | 15 | /api/v1/reports/7c7d9c3f-b09f-4df0-88d9-c9704bb877e7/view |
| 869c472c-548f-43a6-9da1-0f20bf655a4c | completed | 703 | 3 | 16 | 5 | 16 | /api/v1/reports/869c472c-548f-43a6-9da1-0f20bf655a4c/view |
| 18d431ad-054c-4593-9dcb-6ad4f182c973 | completed | 895 | 3 | 17 | 5 | 17 | /api/v1/reports/18d431ad-054c-4593-9dcb-6ad4f182c973/view |

## Gate Outcomes
- `scripts/canary_rollout_smoke.py --snapshot-json /tmp/rollout_window.json ...`:
  - `success_rate=1.0`
  - `p95_duration_seconds=895`
  - `evidence_completeness_rate=1.0`
  - `failed_reason_topN=[]`
  - `go_no_go=go`
- `scripts/rollout_guard.py --snapshot-json /tmp/rollout_window.json`:
  - `action=continue`
  - `reason=all_gates_passed`

## Rollback Drill
- `scripts/rollback_smoke.py` output:
  - `backend=dramatiq`
  - `default_backend_is_dramatiq=True`
  - `actor_path_available=True`
  - `rollback_ready=True`
  - `go_no_go_reason=ready`

## Mandatory Verification
- `PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py` -> pass, collect completed in 12.8s
- `PYTHONPATH=. ./venv/bin/pytest --collect-only -q` -> `324 tests collected`
- `PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py --runs-count 1 --network-count 1 --domains-count 1 --report-img-count 1` -> go
- `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py` -> rollback_ready=true

## Open Risks
1. 当前窗口样本仅 3 个任务，尚未覆盖“真实 10% 流量连续 2-4 小时”观察面。
2. `success_rate` 与 `evidence_completeness_rate` 已满足门禁，但仍需更长窗口观察尾部抖动。
3. 本报告中的 Dramatiq 窗口来自已完成 canary 样本，建议下一窗口按批次继续采样。

## Recommendation
- **GO（按当前决策通过）**：Phase 3 通过并进入下一阶段执行。
- 保留项（非阻塞）：补齐更长窗口与更大样本，用于提升统计置信度与后续放量质量。
