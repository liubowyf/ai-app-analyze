# Phase 4 Exit Report (Scheduling-Only)

**Date:** 2026-03-02  
**Scope:** 仅调度验证（不执行真实远程 APK 分析）  
**Constraints Check:** `TASK_BACKEND` 默认仍为 `dramatiq`，Dramatiq 路径保留。

## 1. Phase 4.1 NO-GO 证据

### 1.1 rollback_now（卡死）
- Snapshot: `/tmp/phase4_window.json`
- 关键字段：
  - `total_tasks=3`
  - `stuck_tasks=3`
  - `success_rate=0.0`
  - `rollback_ready=true`
  - `can_enqueue=true`
- Guard 命令：
  - `PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/phase4_window.json --validation-mode scheduling`
- Guard 结果：
  - `action=rollback_now`
  - `reason=scheduling_stuck_tasks_detected`
  - exit code `1`

### 1.2 hold（样本不足）
- Snapshot: `/tmp/phase41_after.json`
- 关键字段：
  - `total_tasks=0`
  - `stuck_tasks=0`
  - `success_rate=0.0`
  - `rollback_ready=true`
  - `can_enqueue=true`
- Guard 命令：
  - `PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/phase41_after.json --validation-mode scheduling`
- Guard 结果：
  - `action=hold`
  - `reason=insufficient_sample_size`
  - exit code `2`

## 2. Phase 4.2 GO 证据

### 2.1 样本积累（30）
- Samples: `/tmp/phase42_samples.json`
- 关键字段：
  - `count_requested=30`
  - `total_tasks=30`
  - `completed=30`
  - `failed=0`
  - `stuck=0`
  - `success_rate=1.0`
  - `p95_queue_to_start_seconds=1`

### 2.2 窗口快照与门禁
- Snapshot: `/tmp/phase42_window.json`
- 关键字段：
  - `total_tasks=30`
  - `stuck_tasks=0`
  - `success_rate=1.0`
  - `rollback_ready=true`
  - `can_enqueue=true`
- Guard 命令：
  - `PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/phase42_window.json --validation-mode scheduling`
- Guard 结果：
  - `action=continue`
  - `reason=all_gates_passed`
  - exit code `0`

### 2.3 回滚就绪性
- 命令：
  - `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`
- 结果：
  - `rollback_ready=True`
  - `go_no_go_reason=ready`

## 3. 最终决策
- **Decision: GO（可进入下一阶段）**
- 决策依据：
  - 已完成从 `rollback_now/hold` 到 `continue` 的闭环。
  - `total_tasks >= min_sample(30)` 且 `stuck_tasks=0`。
  - `rollback_ready=True`。

## 4. 风险与回滚条件

### Top Risks
1. 样本仍是 probe 调度样本，不能代表真实远程分析链路质量。
2. 历史遗留任务可能再次形成卡滞，需要持续执行卡滞恢复节流策略。
3. 队列/数据库波动可能导致 `total_tasks` 回落，门禁再次进入 `hold`。

### Rollback Triggers
- `action=rollback_now`（任意原因）
- `stuck_tasks > 0`
- `can_enqueue=false`
- `rollback_ready=false`

### Immediate Rollback Command
```bash
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## 5. Repro Command Pack
```bash
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
PYTHONPATH=. ./venv/bin/python scripts/generate_scheduling_samples.py --count 30 --timeout-seconds 180 --output /tmp/phase42_samples.json
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py --minutes 30 --output /tmp/phase42_window.json
PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/phase42_window.json --validation-mode scheduling
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```
