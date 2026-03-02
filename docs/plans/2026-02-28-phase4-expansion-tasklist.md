# Phase 4 Expansion Tasklist (Scheduling-First)

**Purpose:** 在不执行真实远程 APK 全链路的前提下，验证队列/调度/状态机/回滚稳定性。  
**Baseline:** Phase 3 已完成，默认配置保持 `TASK_BACKEND=dramatiq`。

## Global Constraints
- 不修改 `core/config.py` 默认值：`TASK_BACKEND=dramatiq`。
- 不删除 Dramatiq 路径：`enqueue_analysis_workflow` 必须保留。
- 切流仅允许运行时环境变量，不允许硬编码切流。
- 每轮门禁默认执行 `validation_mode=scheduling`。

## Task A: Canary Smoke Scheduling Mode
**Work**
- `scripts/canary_rollout_smoke.py` 新增 `--validation-mode`（`scheduling/e2e`，默认 `scheduling`）。
- `scheduling` 模式只验证调度健康，不依赖 `network/domains/img`。
- 输出统一字段：
  - `go_no_go`
  - `go_no_go_reason`
  - `success_rate`
  - `stuck_tasks`
  - `retry_recovered_rate`
  - `p95_queue_to_start_seconds`
  - `backend`
  - `can_enqueue`

**Pass Gate**
- 无远程分析证据时仍能判定。
- reason 枚举稳定。

## Task B: Scheduling Window Snapshot
**Work**
- 新增 `scripts/scheduling_window_snapshot.py`。
- 从 DB 聚合窗口指标：`queued/running/completed/failed/retrying/stuck`。
- 输出 JSON 快照供 guard 消费。

**Pass Gate**
- 无外设依赖即可产出快照。
- 空窗口与字段缺失场景有可解释输出。

## Task C: Rollout Guard Scheduling Rules
**Work**
- `scripts/rollout_guard.py` 增加 `--validation-mode scheduling` 规则。
- 默认规则（可通过参数调整）：
  - `success_rate >= 0.95`
  - `stuck_tasks == 0`
  - `can_enqueue == true`
  - `rollback_ready == true`

**Pass Gate**
- 通过时：`action=continue`。
- 任一失败：`action=rollback_now` 且 reason 唯一明确。

## Task D: Scheduling Diagnostics API
**Work**
- 在 `/api/v1/tasks/metrics/scheduling` 暴露调度诊断字段：
  - `backend`
  - `can_enqueue`
  - `queued_count`
  - `running_count`
  - `stuck_count`
  - `timestamp`

**Pass Gate**
- 不跑真实 APK 也可持续观察调度健康度。
- 字段命名与 guard/snapshot 对齐。

## Task E: Docs + Exit Template
**Work**
- `docs/TESTING_GUIDE.md` 增补 Phase 4 scheduling 命令。
- 更新本任务清单中的门禁基线。
- 维护 Phase 4 exit report 模板：结论基于调度证据而非远程 E2E。

**Pass Gate**
- 文档命令可直接执行。
- 明确“真实远程 APK 验证属于专项 E2E，不是每轮门禁”。

## Phase 4.1: Scheduling Stuck Remediation (NO-GO Closure)
**Work**
- 扩展 `scheduling_window_snapshot` 输出卡死分类：
  - `stuck_by_status`
  - `stuck_by_age_bucket`（`>5m`/`>15m`/`>30m`）
  - `suspected_reason`（`worker_unavailable`/`lease_blocked`/`retry_backoff`/`unknown`）
- 新增 `recover_stuck_tasks.py`：
  - `--dry-run` 预演
  - `--apply` 执行恢复
  - 幂等（重复执行不重复变更已恢复任务）
- `rollout_guard` scheduling 规则修正：
  - `stuck_tasks > 0` => `rollback_now`
  - `total_tasks < min_sample` => `hold`
  - `total_tasks >= min_sample` 后再判 `success_rate`

**Gate Flow**
- NO-GO（before snapshot）-> recover -> after snapshot -> guard复测。
- 仅调度验证，不触发真实远程 APK 分析链路。

## Phase 4.2: Sample Accumulation for Hold -> Continue
**Work**
- 新增 `scripts/generate_scheduling_samples.py`：
  - 参数：`--count`、`--priority-mix`、`--timeout-seconds`、`--output`
  - 仅执行 probe 状态迁移：`pending -> queued -> static -> dynamic -> report -> completed`
  - 不触发模拟器/mitm/AI 远程分析
- 使用样本生成 + 窗口快照复跑 guard，目标从 `hold` 收敛到 `continue`。

**Pass Gate**
- `total_tasks >= min_sample`（默认 `min_sample=30`）
- `stuck_tasks = 0`
- `action=continue`
- `rollback_ready=true`

## Mandatory Verification Commands
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_canary_smoke_scheduling_mode.py \
  tests/test_scheduling_window_snapshot.py \
  tests/test_rollout_guard.py \
  tests/test_tasks_router_scheduling_metrics.py

PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py --minutes 30 --output /tmp/phase4_window.json
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py --validation-mode scheduling --snapshot-json /tmp/phase4_window.json
PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/phase4_window.json --validation-mode scheduling
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## Release Gate (One-Command)
```bash
bash scripts/phase4_gate_check.sh
```

Decision Matrix:
- `continue` -> GO，进入下一阶段。
- `hold` -> 继续样本积累（推荐执行 `generate_scheduling_samples.py --count 30` 后重试）。
- `rollback_now` -> NO-GO，立即回滚并排查门禁失败原因。
