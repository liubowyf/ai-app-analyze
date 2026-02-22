# 交互引擎与网络监测增量升级设计

## 目标
在保持现有动态分析主流程不变（`workers/dynamic_analyzer.py -> AppExplorer + TrafficMonitor`）的前提下，提升自动交互鲁棒性与网络日志可归因能力，降低报告噪声并提升覆盖率。

## 设计原则
- 增量改造：不推翻 4 阶段探索与 mitmproxy 主链路。
- 可恢复：统一停滞检测与分级恢复策略。
- 可解释：探索与抓包结果带状态/来源/归因元数据。
- 可配置：通过环境变量控制策略阈值和过滤规则。

## 交互引擎改造
- 新增 `ExplorationPolicy`：集中管理步数、停滞阈值、每页点击上限、控件黑白名单、恢复开关。
- 新增 `StateDetector`：以 `activity + window + ui_hash + screenshot_hash` 建模页面状态并做停滞判断。
- 新增 `DialogHandler`：统一弹窗识别（权限/隐私/升级/公告/广告/引导/评分）。
- 新增 `UIExplorer`：UI 树可点击控件枚举、去重、打分与优先级选择。
- 新增 `RecoveryManager`：`back -> home_relaunch -> force_stop_relaunch -> clear_data_relaunch -> reinstall` 分级恢复。
- `AppExplorer.phase3_autonomous_explore` 接入上述策略，并记录 state 元数据。

## 网络监测改造
- 新增 `AttributionEngine`：补充 `package_name/uid/process/source/confidence` 元数据。
- 新增 `TrafficFilterPolicy`：支持 strict target package、包名/UID 包含过滤、系统域名/进程前缀排除。
- `TrafficMonitor` 支持：
  - 按包名/UID/进程过滤查询
  - 请求来源标注（`okhttp/webview/system/unknown`）
  - 按 `host+path+method` 聚合
- `dynamic_analyzer` 输出新增 `network_aggregated`。

## 风险与限制
- 当前归因属于 best-effort（基于请求头+前台包名+系统映射），非内核级强归因。
- 强 HTTPS Pinning 场景仍需后续引入 tcpdump/hybrid backend 才能继续提升覆盖。

## 验证策略
- 单元/运行时测试覆盖新增策略模块与集成路径。
- 回归测试覆盖 AppExplorer、TrafficMonitor、AndroidRunner、mitmproxy integration。
