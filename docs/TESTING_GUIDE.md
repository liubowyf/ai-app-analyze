# 测试执行指南（当前生效）

**版本**: v2.3  
**更新时间**: 2026-03-02

## 0. 当前迭代强制前提（调度验证优先）
- 本阶段所有开发/测试任务默认采用“只验证调度链路”模式：仅验证入队、分发、重试、状态迁移与回滚能力。
- 默认不执行真实远程 APK 分析（不依赖真实模拟器交互、mitm 抓包、AI 远程推理）作为每轮改动验收条件。
- 每轮改动的最小验收以以下证据为准：`pytest` 目标测试通过 + `verify_collect_stability.py` 通过 + `pytest --collect-only -q` 通过。
- 真实远程 APK 全链路验证仅在“专项 E2E 验证”中执行，不作为日常迭代门禁。

## 1. 范围说明
- 当前仓库以 `tests/test_*.py` 为主测试集。
- `tests/task_tests/` 已在 2026-02-27 下线，不再作为可执行测试入口。

## 2. 环境准备
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. 常用命令
```bash
# 收集稳定性门禁（30s 超时，CI/本地都建议先跑）
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py

# 收集测试（推荐先执行）
PYTHONPATH=. ./venv/bin/pytest --collect-only -q

# 全量测试
PYTHONPATH=. ./venv/bin/pytest -v

# 覆盖率
PYTHONPATH=. ./venv/bin/pytest --cov=. --cov-report=html

# 单文件测试示例
PYTHONPATH=. ./venv/bin/pytest -q tests/test_reports_api_simple.py
PYTHONPATH=. ./venv/bin/pytest -q tests/test_emulator_lease.py tests/test_proxy_port_lease.py
```

## 3.1 Phase 2 收口命令
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

PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
```

## 3.2 Phase 2.2 Canary Readiness 命令
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
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
```

## 3.3 Phase 2.3-R2 Canary/Rollback 收口命令
```bash
# 证据门禁（示例阈值：screenshots>0、network>0、domains>0）
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py \
  --runs-count 3 \
  --network-count 10 \
  --domains-count 3 \
  --report-img-count 1

# Dramatiq 运行就绪门禁
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

Canary 验收阈值（最低要求）：
- `report_img_count > 0`
- `network_count > 0`
- `domains_count > 0`
- `runs_count > 0`

## 3.4 Phase 3 Rollout Hardening 命令
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_rollout_guard.py \
  tests/test_queue_backend_runtime_status.py \
  tests/test_task_actor_observability.py \
  tests/test_canary_smoke_scripts.py

# 结构化汇总 + 门禁
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py \
  --runs-count 1 \
  --network-count 1 \
  --domains-count 1 \
  --report-img-count 1

# 回滚触发判定（输入 rolling snapshot）
PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py --snapshot-json /tmp/rollout_window.json

# Dramatiq 运行就绪门禁
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## 3.5 Phase 4 Scheduling-First 命令（不依赖真实远程 APK）
```bash
PYTHONPATH=. ./venv/bin/pytest -q \
  tests/test_canary_smoke_scheduling_mode.py \
  tests/test_scheduling_window_snapshot.py \
  tests/test_rollout_guard.py \
  tests/test_tasks_router_scheduling_metrics.py

PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q

# 生成 30 分钟调度窗口快照
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py \
  --minutes 30 \
  --output /tmp/phase4_window.json

# scheduling 门禁判定（默认模式）
PYTHONPATH=. ./venv/bin/python scripts/canary_rollout_smoke.py \
  --validation-mode scheduling \
  --snapshot-json /tmp/phase4_window.json

# rollout guard 判定
PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py \
  --snapshot-json /tmp/phase4_window.json \
  --validation-mode scheduling

# Dramatiq 运行就绪性
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## 3.6 Phase 4.1 调度卡死修复闭环（NO-GO -> 修复 -> 复测）
```bash
# 1) 基线快照（通常会看到 stuck_tasks>0 导致 NO-GO）
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py \
  --minutes 30 \
  --output /tmp/phase41_before.json

PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py \
  --snapshot-json /tmp/phase41_before.json \
  --validation-mode scheduling

# 2) 卡死恢复（先预演再应用）
PYTHONPATH=. ./venv/bin/python scripts/recover_stuck_tasks.py --dry-run
PYTHONPATH=. ./venv/bin/python scripts/recover_stuck_tasks.py --apply

# 3) 修复后复测
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py \
  --minutes 30 \
  --output /tmp/phase41_after.json

PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py \
  --snapshot-json /tmp/phase41_after.json \
  --validation-mode scheduling
```

判定约束（scheduling）：
- `stuck_tasks > 0` => `rollback_now`
- `total_tasks < min_sample` => `hold`
- 仅当 `total_tasks >= min_sample` 时才判 `success_rate`
- `can_enqueue=false` 或 `rollback_ready=false` => `rollback_now`

## 3.7 Phase 4.2 样本积累（hold -> continue）
```bash
# 1) 生成调度样本（仅 probe 状态迁移，不触发真实远程分析）
PYTHONPATH=. ./venv/bin/python scripts/generate_scheduling_samples.py \
  --count 30 \
  --priority-mix normal:0.8,urgent:0.1,batch:0.1 \
  --timeout-seconds 180 \
  --output /tmp/phase42_samples.json

# 2) 生成窗口快照
PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py \
  --minutes 30 \
  --output /tmp/phase42_window.json

# 3) guard 判定（默认 min_sample=30）
PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py \
  --snapshot-json /tmp/phase42_window.json \
  --validation-mode scheduling
```

hold -> continue 验收标准：
- `total_tasks >= 30`
- `stuck_tasks = 0`
- guard `action=continue`
- `rollback_ready=true`

## 3.8 Phase 4 一键门禁（发布前决策）
```bash
bash scripts/phase4_gate_check.sh
```

结果判定表：
- `action=continue`：允许进入下一阶段（GO）。
- `action=hold`：继续积累样本（执行 `generate_scheduling_samples.py` 后重跑 gate）。
- `action=rollback_now`：立即停止推进并执行回滚路径排查。

## 3.9 Phase 5 连续稳定性门禁（发布前固化）
```bash
# 本地/CI 统一入口（单次）
bash scripts/ci_gate_entry.sh

# 连续门禁（默认 3 次，任一非 continue 即失败）
PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3

# 每日巡检（失败会输出 alert payload JSON）
PYTHONPATH=. ./venv/bin/python scripts/daily_gate_healthcheck.py
```

CI 阻断规则：
- `bash scripts/ci_gate_entry.sh` 返回非 `0` 必须阻断流水线。
- 输出缺失 `final_action` 或 `final_reason` 视为门禁失败。

标准处置动作：
- `continue`：允许发布推进。
- `hold`：暂停发布，先执行样本积累，再重复 `phase5_stability_check`。
- `rollback_now`：立即按回滚手册执行回退，冻结扩流并开启故障排查。

## 4. 分层建议
- API 路由层: `tests/test_api_main.py`, `tests/test_apk_router.py`, `tests/test_tasks_router.py`, `tests/test_reports_api_simple.py`
- 动态分析核心: `tests/test_dynamic_analyzer_minimal.py`, `tests/test_dynamic_analyzer_retry.py`, `tests/test_traffic_monitor_runtime.py`
- 探索与 AI: `tests/test_exploration_*.py`, `tests/test_ai_driver_*.py`
- 域名分析: `tests/test_domain_analyzer*.py`, `tests/test_feature_extractor.py`, `tests/test_ml_classifier.py`
- 报告生成: `tests/test_report_generator_runtime.py`, `tests/test_html_generator.py`
- 租约并发: `tests/test_emulator_lease.py`, `tests/test_proxy_port_lease.py`

## 5. 当前基线
- 最近一次收集结果：`349 tests collected`。
- 若收集数量突降，优先检查：测试文件命名、导入路径、fixture 变更。

## 6. 故障排查
- `ModuleNotFoundError`：确认使用了 `PYTHONPATH=.`。
- 与外部依赖相关失败：优先使用 mock fixture，而不是直接依赖真实 MySQL/Redis/MinIO/模拟器。
- 长耗时测试：先按文件分组跑，再定位具体失败用例。
