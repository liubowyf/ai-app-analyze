# 数据持久化现状说明

**更新日期**: 2026-02-23  
**适用版本**: 当前主干（RabbitMQ + MySQL 分布式租约）

## 1. 目标
- 保证动态分析结果可检索、可归因、可追踪。
- 支持分布式部署下的并发任务安全执行。
- 为接口调用方提供稳定的查询面（任务状态、阶段轨迹、网络证据、域名证据）。

## 2. 持久化分层
- 业务元数据: MySQL（任务、分析结果、运行轨迹、租约状态）。
- 大文件对象: MinIO（APK、报告、截图对象）。
- 任务队列: RabbitMQ（Celery broker）；结果后端 `rpc://`。

## 3. 当前已落地的数据表
- `tasks`: 任务主记录（状态、错误、结果引用等）。
- `static_analysis`: 静态分析归一化结果。
- `dynamic_analysis`: 动态分析摘要（步数、活动数、请求数、成功状态等）。
- `network_requests`: 网络请求明细（host/path/method/source/package/uid 等）。
- `master_domains`: 主控域名分析结果。
- `screenshots`: 截图元数据（stage/description/storage_path）。
- `analysis_runs`: 分阶段执行轨迹（stage/attempt/status/duration/error/emulator）。
- `emulator_leases`: 模拟器分布式租约（防止多 worker 抢同一模拟器）。
- `proxy_port_leases`: 代理端口分布式租约（防止并发抓包端口冲突）。

## 4. 写入路径
- `workers/static_analyzer.py`: 写 `tasks.static_analysis_result` + `analysis_runs(static)`。
- `workers/dynamic_analyzer.py`:
  - 写 `tasks.dynamic_analysis_result`（兼容字段）；
  - 写归一化表 `dynamic_analysis/network_requests/master_domains/screenshots`；
  - 写 `analysis_runs(dynamic)`；
  - 动态阶段执行前后写 `emulator_leases`、`proxy_port_leases`。
- `workers/report_generator.py`: 写 `tasks.report_storage_path` + `analysis_runs(report)`。

## 5. 查询接口（已对外）
- `GET /api/v1/tasks/{task_id}`: 任务总体状态与结果引用。
- `GET /api/v1/tasks/{task_id}/runs`: 分阶段运行轨迹。
- `GET /api/v1/tasks/{task_id}/network-requests`: 网络请求明细（支持分页与 host 过滤）。
- `GET /api/v1/tasks/{task_id}/domains`: 主控域名结果。

## 6. 运行与一致性约束
- 动态任务必须先成功获取:
  - 模拟器租约（`emulator_leases`）；
  - 代理端口租约（`proxy_port_leases`）。
- 任一租约不可用时，任务进入 Celery retry，不直接失败。
- 动态任务结束时必须释放租约并清理设备代理设置，避免污染后续任务。

## 7. 当前已知边界
- HTTPS 明文抓取仍受目标 App 对证书信任策略影响（TLS 握手失败会降低内容可见性）。
- 当前表结构由应用启动 `create_all` 兜底，生产建议逐步收敛到 Alembic 迁移管理。
