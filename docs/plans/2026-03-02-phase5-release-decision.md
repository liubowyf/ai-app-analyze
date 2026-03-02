# Phase 5 Release Decision (Scheduling-Only)

**Date:** 2026-03-02  
**Scope:** 发布前治理与持续门禁固化（仅调度验证，不执行真实远程 APK 分析）

## 1. 输入证据

### 1.1 门禁脚本证据
- Phase 4 单次门禁：`bash scripts/phase4_gate_check.sh`
- Phase 5 连续门禁：`PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3`
- Collect 稳定性：`PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py`
- 全量 collect：`PYTHONPATH=. ./venv/bin/pytest --collect-only -q`

### 1.2 历史基线证据（Phase 4）
- Phase 4.1 NO-GO：`rollback_now (scheduling_stuck_tasks_detected)`、`hold (insufficient_sample_size)`。
- Phase 4.2 GO：`total_tasks >= 30`、`stuck_tasks = 0`、`action=continue`、`rollback_ready=true`。
- 详情见：[docs/plans/2026-02-28-phase4-exit-report.md](/Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统/docs/plans/2026-02-28-phase4-exit-report.md)

### 1.3 本轮（2026-03-02）执行结果
- `PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py`：PASS（约 11.4s）
- `PYTHONPATH=. ./venv/bin/pytest --collect-only -q`：PASS（`349 tests collected`）
- 首次 `bash scripts/phase4_gate_check.sh`：`hold`（`insufficient_sample_size`）
- 补样本：`PYTHONPATH=. ./venv/bin/python scripts/generate_scheduling_samples.py --count 30 --timeout-seconds 180 --output /tmp/phase5_samples.json`
- 复跑 `bash scripts/phase4_gate_check.sh`：PASS（`final_action=continue`，`final_reason=all_gates_passed`）
- 复跑 `PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3`：PASS（三次均 `continue`）

## 2. 门禁结论
- 决策口径：
  - `continue` => GO
  - `hold` => 样本不足，继续积累样本后复检
  - `rollback_now` => NO-GO，立即回滚并排障
- 本次发布前要求：连续 3 次门禁均为 `continue`，且 `rollback_smoke` 每次均 ready。
- **当前结论（本轮）**：`GO`（通过条件：3 次门禁均 `continue`，且 rollback smoke ready）。

## 3. 上线前提
1. 默认配置不变：`core/config.py` 中 `TASK_BACKEND` 保持 `dramatiq`。
2. Dramatiq 路径保留：`enqueue_analysis_workflow` 不删除。
3. 运行时切流仅通过环境变量，不允许硬编码。
4. `phase4_gate_check` 与 `phase5_stability_check` 均可一键执行并输出 `final_action/final_reason`。

## 4. 回滚条件
1. 任一门禁输出 `rollback_now`。
2. 任一门禁输出 `hold` 且在约定时间窗内无法恢复到 `continue`。
3. `rollback_smoke` 非 ready。

## 5. 值班人
- Primary Oncall: `TBD`（发布前填写）
- Secondary Oncall: `TBD`（发布前填写）
- DBA/Infra Backup: `TBD`（发布前填写）

## 6. 可复现命令
```bash
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
PYTHONPATH=. ./venv/bin/pytest --collect-only -q
bash scripts/phase4_gate_check.sh
PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3
```
