# 测试快速参考（当前生效）

## 一次性命令
```bash
# 收集稳定性门禁（30s）
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py

# 收集测试
PYTHONPATH=. ./venv/bin/pytest --collect-only -q

# 全量回归
PYTHONPATH=. ./venv/bin/pytest -q

# 关键回归（报告 + 租约）
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_reports_api_simple.py \
  tests/test_report_generator_runtime.py \
  tests/test_emulator_lease.py \
  tests/test_proxy_port_lease.py
```

## Phase 2 集成门禁
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
```

## Phase 2.2 Canary Readiness 门禁
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_queue_backend.py \
  tests/test_queue_backend_dramatiq_path.py \
  tests/test_queue_backend_runtime_status.py \
  tests/test_tasks_router.py \
  tests/test_task_actor_state_machine_runtime.py \
  tests/test_task_actor_retry_lock.py \
  tests/test_task_actor_observability.py

PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## Phase 2.3-R2 证据门禁
```bash
# evidence 为空时会返回 no-go
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py \
  --runs-count 3 \
  --network-count 10 \
  --domains-count 3 \
  --report-img-count 1

PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

Canary 最低阈值：
- `runs_count > 0`
- `network_count > 0`
- `domains_count > 0`
- `report_img_count > 0`

## Phase 3 Rollout Hardening
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_rollout_guard.py \
  tests/test_queue_backend_runtime_status.py \
  tests/test_task_actor_observability.py \
  tests/test_canary_smoke_scripts.py

PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py \
  --runs-count 1 \
  --network-count 1 \
  --domains-count 1 \
  --report-img-count 1

PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/rollout_window.json
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

Phase 3 GO 门禁：
- `success_rate >= 95%`
- `evidence_completeness_rate == 100%`
- 任一触发器命中时 `scripts/rollout_guard.py` 必须返回 `rollback_now`

## 常用分组
```bash
# API
PYTHONPATH=. ./venv/bin/pytest -q tests/test_api_main.py tests/test_apk_router.py tests/test_tasks_router.py

# Dynamic/Traffic
PYTHONPATH=. ./venv/bin/pytest -q tests/test_dynamic_analyzer_minimal.py tests/test_traffic_monitor_runtime.py

# AI/Exploration
PYTHONPATH=. ./venv/bin/pytest -q tests/test_ai_driver_runtime.py tests/test_exploration_controller.py tests/test_exploration_policy.py

# Domain Analyzer
PYTHONPATH=. ./venv/bin/pytest -q tests/test_domain_analyzer.py tests/test_domain_analyzer_ml.py tests/test_feature_extractor.py
```

## 说明
- `tests/task_tests/` 已下线，不再使用其中命令。
- 新增/修改功能后，至少执行“收集 + 对应模块分组测试”。
- 队列后端已统一为 `TASK_BACKEND=dramatiq`（Dramatiq-only）。
