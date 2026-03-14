# Context Index

目的：降低后续 agent 的上下文加载量，只保留最小读取路径。本文档不描述实现细节，只描述“先读什么、在哪找什么”。

## 最小读取顺序
1. `docs/CURRENT_STATE.md`
   - 当前唯一真实状态
   - 架构、环境变量、运行链路、验收口径、成功样本
2. `docs/CONTEXT_INDEX.md`（本文）
   - 压缩后的内容索引
   - 按问题定位到代码与文档
3. `deploy/redroid-host-agent/docker-compose.yml`
   - 仅在需要核对 host-agent 节点 host-agent 部署方式与环境变量时读取
4. `deploy/frontend/docker-compose.yml` / `deploy/backend/docker-compose.yml` / `deploy/worker/docker-compose.yml`
   - 仅在需要核对 24/25/23 三节点生产部署时读取

## 不需要默认加载的内容
- 历史方案、历史验证、历史迁移文档：已删除
- 旧 Android Docker / MITM / no-mitm 资料：已删除，不再作为现状依据
- 除非要改代码，否则不要先读整个仓库

## 当前系统一句话
系统当前仅保留一条动态分析主线：
`页面上传 APK -> FastAPI 建任务 -> Dramatiq worker -> redroid_remote -> 远程 ADB 控制 redroid -> redroid-host-agent 启停 tcpdump/运行 Zeek/回传日志 -> MySQL 落库 -> MinIO 存截图与报告 -> 前端详情页/报告页展示`

## 读代码的最小入口

### 1. 服务与配置
- `core/config.py`
  - 当前后端与基础设施配置
  - `ANALYSIS_BACKEND=redroid_remote`
- `deploy/frontend/docker-compose.yml`
  - frontend 节点前端部署入口
  - 依赖 `NEXT_PUBLIC_API_BASE_URL`
- `deploy/backend/docker-compose.yml`
  - api 节点 API 部署入口
  - 支持 `APP_SOURCE_DIR` 挂载源码做增量发布
- `deploy/worker/docker-compose.yml`
  - worker 节点 Worker 部署入口
  - 支持 `APP_SOURCE_DIR` 挂载源码做增量发布
- `api/main.py`
  - API 启动入口
- `scripts/dev_up.sh`
  - 本地测试环境推荐入口
  - 默认加载根目录 `.env`
  - 使用最简单的后台进程启动 API / worker / frontend
- `scripts/start_services.sh`
  - 当前稳定启动方式
  - 默认加载根目录 `.env`
  - 使用 `tmux` 会话 `intelligent-app-api` / `intelligent-app-worker` / `intelligent-app-frontend`

### 2. 任务主链路
- `api/routers/frontend.py`
  - 页面上传、任务列表、任务详情、报告 DTO 接口
- `workers/task_actor.py`
  - 阶段推进：static -> dynamic -> report
- `workers/dynamic_analyzer.py`
  - 动态分析统一入口，分发到 `redroid_remote`
- `workers/report_generator.py`
  - 报告生成与上传

### 3. redroid 方案二主线
- `modules/analysis_backends/redroid_remote.py`
  - 远端动态分析总控
- `modules/redroid_remote/adb_client.py`
  - ADB 连接、安装、启动、截图、UI 导出
- `modules/redroid_remote/host_agent_client.py`
  - host-agent API 客户端
- `modules/redroid_remote/device_controller.py`
  - redroid 设备侧控制封装
- `modules/redroid_remote/traffic_collector.py`
  - 通过 host-agent 启停抓包与 Zeek
- `modules/redroid_remote/traffic_parser.py`
  - 域名、IP、命中次数解析
- `modules/redroid_remote/result_assembler.py`
  - 组装 observation/domain/screenshot 结果
- `host_agent/`
  - host-agent 节点宿主机 Agent 服务
- `deploy/redroid-host-agent/docker-compose.yml`
  - host-agent 节点 compose 部署入口

### 4. AI 交互与截图
- `modules/exploration_strategy/policy.py`
  - 探索预算与阈值，当前总操作/截图预算为 25
- `modules/exploration_strategy/explorer.py`
  - AI 驱动点击、输入、截图、页面恢复
- `modules/android_runner/runner.py`
  - ADB 通用执行与 APK 安装，安装超时当前为 600 秒

### 5. 持久化与展示
- `models/analysis_tables.py`
  - 任务、运行记录、网络观测、域名、截图表
- `core/storage.py`
  - MinIO 存储
- `modules/frontend_presenters/task_detail.py`
  - 详情页 DTO
- `modules/frontend_presenters/report.py`
  - 报告页 DTO
- `frontend/app/tasks/[taskId]/page.tsx`
  - 任务详情页
- `frontend/app/reports/[taskId]/page.tsx`
  - 报告页

## 按问题定位

### 页面打不开 / 样式丢失 / 静态资源异常
先看：
- `scripts/start_services.sh`
- `.runtime_logs/frontend.log`
- `frontend/app/layout.tsx`
- `frontend/lib/api.ts`

### 上传 APK 一直卡住 / 创建任务慢
先看：
- `api/routers/frontend.py`
- `modules/upload_batch/service.py`
- `.runtime_logs/api.log`
- MySQL / MinIO 连接状态

### 任务进入 static 但不推进
先看：
- `workers/task_actor.py`
- `.runtime_logs/worker.log`
- `analysis_runs` 表

### 动态分析失败
先看：
- `workers/dynamic_analyzer.py`
- `modules/analysis_backends/redroid_remote.py`
- `host_agent/services/capture_service.py`
- `.runtime_logs/worker.log`

### 没有网络域名/IP统计
先看：
- `modules/redroid_remote/traffic_collector.py`
- `modules/redroid_remote/traffic_parser.py`
- `host_agent/services/file_service.py`
- 远端抓包输出与 Zeek 产物
- `network_requests` / `master_domains` 表

### 有截图日志但页面不显示截图
先看：
- `core/storage.py`
- `modules/frontend_presenters/task_detail.py`
- `modules/frontend_presenters/report.py`
- `frontend/lib/api.ts`

### 详情页/报告页数据不对
先看：
- `api/routers/frontend.py`
- `modules/frontend_presenters/task_detail.py`
- `modules/frontend_presenters/report.py`

## 当前成功样本
- 任务：`00ff992d-95eb-4cdc-b7b9-9d7195a7184a`
- 验收结果：
  - `completed`
  - `screenshots = 10`
  - `network_requests = 196`
  - `domains = 17`
  - `unique_ips = 30`
  - `capture_mode = redroid_zeek`
- 页面：
  - `/tasks/00ff992d-95eb-4cdc-b7b9-9d7195a7184a`
  - `/reports/00ff992d-95eb-4cdc-b7b9-9d7195a7184a`

## 后续上下文压缩原则
- 默认只加载：`docs/CURRENT_STATE.md` + `docs/CONTEXT_INDEX.md`
- 只有当问题涉及 host-agent 节点部署时，再加载 `deploy/redroid-host-agent/docker-compose.yml`
- 只有当问题涉及 24/25/23 三节点生产部署时，再加载对应 `deploy/*/docker-compose.yml`
- 只有当具体模块需要修复时，再打开对应代码文件
