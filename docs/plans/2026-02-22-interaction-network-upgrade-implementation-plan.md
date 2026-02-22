# Interaction & Network Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将自动交互升级为可恢复可探索策略，并将流量监测升级为可归因可过滤输出。

**Architecture:** 保留既有 `AppExplorer` 四阶段与 `TrafficMonitor` mitmproxy 主链路，在 `modules/exploration_strategy` 与 `modules/traffic_monitor` 新增策略/归因组件并注入现有流程。`workers/dynamic_analyzer.py` 只做参数与输出对接。

**Tech Stack:** Python, pytest, FastAPI/Celery 现有架构, ADB, mitmproxy.

---

### Task 1: 交互策略模块化

**Files:**
- Create: `modules/exploration_strategy/policy.py`
- Create: `modules/exploration_strategy/state_detector.py`
- Create: `modules/exploration_strategy/dialog_handler.py`
- Create: `modules/exploration_strategy/ui_explorer.py`
- Create: `modules/exploration_strategy/recovery_manager.py`
- Test: `tests/test_exploration_policy.py`
- Test: `tests/test_exploration_state_detector.py`
- Test: `tests/test_recovery_manager.py`

**Step 1: Write failing tests**
- 编写策略解析、状态停滞检测、恢复分级动作测试。

**Step 2: Run tests to verify RED**
- Run: `PYTHONPATH=. ./venv/bin/pytest -q tests/test_exploration_policy.py tests/test_exploration_state_detector.py tests/test_recovery_manager.py -q`
- Expected: `ModuleNotFoundError` 或断言失败。

**Step 3: Implement minimal modules**
- 实现 policy/state/dialog/ui/recovery。

**Step 4: Run tests to verify GREEN**
- Run 同 Step 2。
- Expected: 全部通过。

### Task 2: AppExplorer 集成改造

**Files:**
- Modify: `modules/exploration_strategy/explorer.py`
- Modify: `modules/android_runner/runner.py`
- Test: `tests/test_app_explorer.py`

**Step 1: Write/keep failing integration behavior tests**
- 覆盖弹窗优先处理、前台漂移恢复、UI fallback 点击、skip 页面判定。

**Step 2: Run tests to verify RED**
- Run: `PYTHONPATH=. ./venv/bin/pytest -q tests/test_app_explorer.py -q`

**Step 3: Implement integration**
- explorer 注入 policy/state/dialog/ui/recovery。
- runner 增加 `get_current_window/dump_ui_hierarchy/force_stop_app/clear_app_data`。

**Step 4: Run tests to verify GREEN**
- Run 同 Step 2。

### Task 3: TrafficMonitor 归因与过滤升级

**Files:**
- Create: `modules/traffic_monitor/attribution.py`
- Create: `modules/traffic_monitor/filter_policy.py`
- Modify: `modules/traffic_monitor/monitor.py`
- Test: `tests/test_traffic_monitor_runtime.py`

**Step 1: Write/extend failing tests**
- 覆盖 source 标注、package/uid/process 过滤、聚合输出、系统噪声过滤。

**Step 2: Run tests to verify RED**
- Run: `PYTHONPATH=. ./venv/bin/pytest -q tests/test_traffic_monitor_runtime.py -q`

**Step 3: Implement minimal code**
- monitor 接入 attribution/filter policy，并新增聚合 API。

**Step 4: Run tests to verify GREEN**
- Run 同 Step 2。

### Task 4: Dynamic Analyzer 对接

**Files:**
- Modify: `workers/dynamic_analyzer.py`

**Step 1: Add runtime policy wiring**
- 注入 `ExplorationPolicy.from_env()`。
- 注入 `TrafficMonitor.set_filter_policy(...)`。

**Step 2: Add output payload enhancements**
- 新增 `network_aggregated` 输出。

**Step 3: Verification**
- Run: `PYTHONPATH=. ./venv/bin/pytest -q tests/test_app_explorer.py tests/test_traffic_monitor_runtime.py -q`

### Task 5: 回归验证与APK实测

**Files:**
- Verify: `tests/test_android_runner_enhanced.py`
- Verify: `tests/test_mitmproxy_integration_runtime.py`
- Verify: `tests/test_exploration_controller.py`

**Step 1: Run regression tests**
- Run: `PYTHONPATH=. ./venv/bin/pytest -q tests/test_android_runner_enhanced.py tests/test_mitmproxy_integration_runtime.py tests/test_app_explorer.py tests/test_traffic_monitor_runtime.py tests/test_exploration_controller.py -q`

**Step 2: APK full-flow validation**
- 使用 APK: `/Users/liubo/Downloads/安心借_ca0e0b9cd0522b99f30218ec9269d4f3.apk`
- 在可用依赖环境执行动态分析全流程并记录日志。

**Step 3: Commit**
- `git add ...`
- `git commit -m "feat: upgrade exploration resilience and traffic attribution filtering"`
