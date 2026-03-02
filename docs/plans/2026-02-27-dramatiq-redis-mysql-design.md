# Dramatiq + Redis + MySQL 架构设计（替代 Dramatiq）

**日期**: 2026-02-27  
**作者**: 架构方案草案（可交付执行）

## 1. 背景与问题
当前 Dramatiq Worker 在实际测试中出现任务分发不稳定、阻塞与可观测性不足问题，影响任务全流程稳定性。

目标是在不改变核心业务流程（`static -> dynamic -> report`）前提下，采用更轻量、可控、可恢复的异步架构。

## 2. 设计目标
- 保持异步执行能力与并发处理能力。
- 降低队列系统复杂度（单队列、单 actor 主流程）。
- 把任务真相源收敛到 MySQL（Redis 只做分发）。
- 显式状态机推进，避免“黑盒链式任务”难排障问题。
- 支持平滑迁移与快速回滚。

## 3. 非目标
- 不重写 static/dynamic/report 业务算法。
- 不一次性重构所有数据模型。
- 不在首版引入复杂调度编排平台。

## 4. 目标架构

### 4.1 组件
- API（FastAPI）
  - 创建任务、入队消息。
- Redis Cluster
  - Dramatiq broker，负责任务分发。
- Worker（Dramatiq）
  - 单 actor：`run_task(task_id)`。
- MySQL
  - 任务状态机、阶段轨迹、错误与重试计数。
- MinIO
  - APK、截图、报告对象存储（保持不变）。

### 4.2 核心流程（单队列）
1. API 创建任务，写 `tasks.status=queued`。
2. API 调用 `run_task.send(task_id)`。
3. Worker 消费后读取任务状态，决定当前应执行阶段。
4. 执行阶段函数（static/dynamic/report）。
5. 成功：推进到下一阶段并再次 `send(task_id)`；
   失败：写错误、按退避策略重试或终态失败。
6. 最终状态：`completed` 或 `failed`。

## 5. 状态机设计
使用现有 `TaskStatus` 即可：
- `pending`
- `queued`
- `static_analyzing`
- `dynamic_analyzing`
- `report_generating`
- `completed`
- `failed`

阶段推进映射：
- `queued/pending -> static_analyzing`
- `static_analyzing(success) -> dynamic_analyzing`
- `dynamic_analyzing(success) -> report_generating`
- `report_generating(success) -> completed`

## 6. 一致性与幂等
- Redis 分布式锁：`lock:task:{task_id}`，`SET NX EX` 防并发重复执行。
- 阶段执行前做幂等检查：若阶段已完成则直接推进下一阶段。
- `analysis_runs` 继续记录阶段 attempt/status/duration/error，作为审计与排障主入口。

## 7. 重试与恢复策略
- 重试上限：沿用 `tasks.retry_count` 或新增阶段内重试计数。
- 退避：`10s -> 30s -> 90s -> 180s`（可配置）。
- 重试实现：`run_task.send_with_options(delay=...)`。
- 恢复守护（可选第二阶段）：周期扫描“长时间 running 且超时”的任务并重投。

## 8. 迁移策略（零停机）

### 阶段 A：引入并旁路
- 新增 Dramatiq 运行链路与队列抽象，但不切流量。
- 增加配置开关：`TASK_BACKEND=dramatiq`。

### 阶段 B：灰度切换
- 新建任务走 Dramatiq；已在 Dramatiq 中的任务继续跑完。
- 监控指标：队列堆积、任务成功率、平均时延、失败重试率。

### 阶段 C：完成切换
- 全量切到 Dramatiq。
- 下线 Dramatiq worker 与相关部署脚本。

## 9. 回滚策略
- 将 `TASK_BACKEND` 切回 `dramatiq`。
- 保留 Dramatiq 路径至少一版发布周期，确保随时回退。

## 10. 风险与对策
- 风险：单队列吞吐受限。
  - 对策：先单队列稳定化，后续可按 stage 增加 routing key。
- 风险：阶段函数与 Dramatiq 任务耦合。
  - 对策：抽离 stage service 函数，Dramatiq/Dramatiq 仅做包装调用。
- 风险：重复消费导致重复执行。
  - 对策：Redis 锁 + MySQL 状态机双保险。

## 11. 验收标准
- 上传任务到完成报告全链路稳定通过。
- 不出现“同任务并发重复执行”。
- 阶段失败可自动重试并可审计。
- `runs/network-requests/domains/report view` 接口行为不回退。

