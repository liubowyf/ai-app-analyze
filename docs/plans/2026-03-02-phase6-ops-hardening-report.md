# Phase 6 Ops Hardening Report (Scheduling-Only)

**Date:** 2026-03-02  
**Scope:** 调度门禁产品化（CI 接入、每日巡检、阈值配置化、运维文档收口）

## 1. 实施内容

1. CI 强制门禁接入
- 新增 GitHub Actions 工作流：`.github/workflows/phase6-gate.yml`
- 统一入口：`scripts/ci_gate_entry.sh`
- 行为：非 0 立即失败；强制校验 `final_action/final_reason` 输出完整性。

2. 每日稳定性巡检 + 告警
- 新增：`scripts/daily_gate_healthcheck.py`
- 行为：执行 `phase5_stability_check --runs 3`，失败时输出结构化告警 payload（JSON）。

3. 门禁阈值配置化（默认不变）
- 新增：`scripts/gate_config.py`
- 已配置项：
  - `GATE_COLLECT_TIMEOUT_SECONDS`（默认 30）
  - `GATE_PHASE5_RUNS`（默认 3）
  - `GATE_WINDOW_MINUTES`（默认 30）
  - `GATE_MIN_SAMPLE`（默认 30）
- 接入脚本：
  - `scripts/verify_collect_stability.py`
  - `scripts/phase4_gate_check.py`
  - `scripts/phase5_stability_check.py`
  - `scripts/daily_gate_healthcheck.py`

4. 文档收口
- 更新：`docs/OPERATIONS.md`
- 更新：`docs/TESTING_GUIDE.md`

## 2. 验证结果

- 单元/契约测试：
  - `tests/test_ci_gate_entry_integration.py`
  - `tests/test_daily_gate_healthcheck.py`
  - `tests/test_gate_config_contract.py`
  - 以及既有 phase4/phase5/guard 测试
- 运行门禁验证：
  - `bash scripts/ci_gate_entry.sh`
  - `PYTHONPATH=. ./venv/bin/python scripts/daily_gate_healthcheck.py`
  - `PYTHONPATH=. ./venv/bin/python scripts/phase5_stability_check.py --runs 3`
  - `PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py`

## 3. 残余风险

1. 仍是 scheduling-only 门禁，不能替代专项远程 E2E 证据。  
2. 样本窗口若不足，门禁会进入 `hold`，需要值班执行样本补齐流程。  
3. CI 仅接入 GitHub Actions；若生产使用其他 CI 平台，需等价迁移规则。

## 4. 回滚方案

1. 若门禁异常导致大面积误报，可先将 CI 任务改为手动触发（不删除脚本）。
2. 保持 `scripts/ci_gate_entry.sh` 为唯一入口，逐步回放排障。
3. 任一门禁输出 `rollback_now` 时，执行：

```bash
PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py
```

## 5. 约束核对

- `core/config.py` 默认 `TASK_BACKEND="dramatiq"` 未修改。  
- Dramatiq 路径 `enqueue_analysis_workflow` 保留。  
- 本阶段未引入真实远程 APK 分析依赖（模拟器/mitm/AI 远程推理）。
