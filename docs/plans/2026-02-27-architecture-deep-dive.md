# 当前项目架构深度解析（代码对齐版）

**日期**: 2026-02-27  
**目标**: 用代码真实实现解释系统架构、执行链路、数据模型与关键风险点。

## 1. 总体形态
- 架构本质：`FastAPI + Dramatiq Worker + MySQL + Redis + MinIO + Android 模拟器` 的单仓分层系统。
- 非严格微服务：API 与 Worker 在同一代码库，靠队列进行异步解耦。

## 2. 模块分层
- 接入层：`api/`
- 任务执行层：`workers/`
- 领域能力层：`modules/`
- 基础设施层：`core/`
- 数据模型层：`models/`

## 3. 入口与路由
- FastAPI 启动与路由挂载：`api/main.py`
  - `FastAPI(...)` 初始化
  - 挂载 `/api/v1/apk`, `/api/v1/tasks`, `/api/v1/reports`, `/api/v1/whitelist`
- 静态资源：`/static`

## 4. 核心任务链路
### 4.1 上传触发
- `POST /api/v1/apk/upload`
  - 计算 MD5，写入 `tasks`，APK 上传 MinIO，随后入队工作流。
  - 当前上传路径默认：`include_static=True`（static -> dynamic -> report）。

### 4.2 手动任务触发
- `POST /api/v1/tasks`
  - 将任务置为 `queued`，并入队 `include_static=True`（static -> dynamic -> report）。

### 4.3 编排器
- `modules/task_orchestration/orchestrator.py`
  - `build_analysis_workflow()` 使用 Dramatiq chain。
  - 支持两条链路：
    - `static -> dynamic -> report`
    - `dynamic -> report`

## 5. Worker 执行细节
### 5.1 static
- `workers/static_analyzer.py`
  - 任务状态推进：`STATIC_ANALYZING`
  - APK 下载后执行静态分析，结果写入 `tasks.static_analysis_result`
  - 写阶段轨迹 `analysis_runs(stage=static)`

### 5.2 dynamic
- `workers/dynamic_analyzer.py`
  - 任务状态推进：`DYNAMIC_ANALYZING`
  - 租约：先申请模拟器租约 + 抓包端口租约
  - 执行链：AndroidRunner -> AppExplorer -> TrafficMonitor -> MasterDomainAnalyzer
  - 同时写两类结果：
    - 兼容 JSON：`tasks.dynamic_analysis_result`
    - 归一化表：`dynamic_analysis/network_requests/master_domains/screenshots`
  - 写阶段轨迹 `analysis_runs(stage=dynamic)`

### 5.3 report
- `workers/report_generator.py`
  - 任务状态推进：`REPORT_GENERATING -> COMPLETED/FAILED`
  - 生成 PDF + web HTML + static HTML
  - 上传 MinIO 路径：`reports/{task_id}/...`
  - 写阶段轨迹 `analysis_runs(stage=report)`

## 6. 数据模型
### 6.1 任务主表
- `models/task.py`
  - 任务状态、错误信息、报告路径、兼容 JSON 结果
  - 关联归一化表 relationship

### 6.2 归一化分析表
- `models/analysis_tables.py`
  - `static_analysis`
  - `dynamic_analysis`
  - `network_requests`
  - `master_domains`
  - `screenshots`
  - `analysis_runs`

### 6.3 并发租约表
- `models/emulator_lease.py`
- `models/proxy_port_lease.py`
- 统一 UTC naive 时间函数：`core/time_utils.py`

## 7. 查询面（读路径）
- 任务状态：`GET /api/v1/tasks/{task_id}`
- 运行轨迹：`GET /api/v1/tasks/{task_id}/runs`
- 网络证据：`GET /api/v1/tasks/{task_id}/network-requests`
- 域名证据：`GET /api/v1/tasks/{task_id}/domains`
- 报告查看/下载：
  - `GET /api/v1/reports/{task_id}/view`
  - `GET /api/v1/reports/{task_id}/download`

## 8. 并发与隔离机制
- Dramatiq 队列分离：`static`, `dynamic`, `report`
- 租约机制保证并发安全：
  - 模拟器互斥
  - 代理端口互斥
- 阶段级可观测：`analysis_runs` 记录 stage/attempt/status/duration/error

## 9. 当前架构的关键一致性问题
1. 表创建逻辑分散：API 启动、dynamic worker、run_tracker 都在做 `create_all` 兜底。
2. 文档历史漂移：部分旧文档与当前执行方式不一致（本轮已更新测试文档）。
3. 数据库 SSL 校验配置较弱（`CERT_NONE`），生产需评估收紧。

## 10. 建议的演进优先级
1. 统一工作流策略（upload 与 tasks/retry 行为一致）。
2. 收敛 schema 管理（逐步切 Alembic，减少运行时 `create_all`）。
3. 将“兼容 JSON”与“归一化表”边界写清，避免双写语义歧义。
4. 补齐“动态阶段失败但可部分产出”的可视化标记与 API 字段。
