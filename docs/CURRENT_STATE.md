# 网络反诈中心-智能APP分析平台：当前唯一有效文档

更新时间：2026-03-13

## 1. 当前唯一主线
- 前端：Next.js，主入口 `http://127.0.0.1:3000`
- 后端：FastAPI，主入口 `http://127.0.0.1:8000`
- Worker：Dramatiq
- 动态分析后端：`redroid_remote`
- 宿主机控制面：`redroid-host-agent`
- 动态网络采集：`redroid-host-agent + tcpdump + Zeek`
- 报告主入口：前端页面 `/reports/{taskId}`

## 2. 已彻底废弃，不再恢复
- Android Docker
- 本地 Android 模拟器池
- emulator lease / proxy port lease 方案
- no-mitm / passive_no_mitm 方案
- MITM / internal proxy / adb reverse 观测链
- 后端 HTML 报告主入口 `/api/v1/reports/{task_id}/view`

## 3. 当前运行架构
1. 页面上传 APK
2. API 创建任务并入队
3. Worker 执行静态分析
4. Worker 根据 `ANALYSIS_BACKEND=redroid_remote` 调用远端 redroid 动态分析
5. redroid 动态分析流程：
   - ADB 连接 `<host-agent-node>:16555`
   - 安装 APK
   - 启动 App
   - AI 驱动页面探索、点击、输入
   - 截图与 UI 导出
   - 调用 `redroid-host-agent` 启动宿主机 `tcpdump`
   - 调用 `redroid-host-agent` 运行 Zeek 并拉回 `conn.log / dns.log / ssl.log / http.log`
   - 聚合 `domain / ip / hit_count / source_type`
6. 结果写入 MySQL，截图与报告写入 MinIO
7. 前端详情页和报告页展示结构化结果

## 4. 当前固定基础设施
### 应用服务
- 前端：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8000`

### 生产三节点部署目标
- `frontend`：`<frontend-node>`
- `api`：`<api-node>`
- `worker`：`<worker-node>`
- 生产链路：`用户 -> frontend -> api -> worker -> redroid-host-agent`

### redroid 分析节点
- `redroid-1`：`<host-agent-node>:16555`
- `redroid-2`：`<host-agent-node>:16556`
- `redroid-3`：`<host-agent-node>:16557`
- host-agent：`http://<host-agent-node>:18080`
- 容器：`redroid-1 / redroid-2 / redroid-3`

### 数据与存储
- MySQL：`<host-agent-node>:3306`
- Redis：`<infra-node>:6379`
- MinIO：`<infra-node>:9000`

## 5. 当前环境变量基线
- `ANALYSIS_BACKEND=redroid_remote`
- `REDROID_HOST_AGENT_BASE_URL=http://<host-agent-node>:18080`
- `REDROID_HOST_AGENT_TOKEN=<token>`
- `REDROID_SLOTS_JSON=[redroid-1, redroid-2, redroid-3]`
- `REDROID_LEASE_TTL_SECONDS=1800`
- `REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS=600`
- `ADB_INSTALL_TIMEOUT_SECONDS=600`
- `APP_EXPLORATION_MAX_STEPS=25`
- `APP_EXPLORATION_TOTAL_ACTION_BUDGET=25`
- `APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET=25`

## 6. 数据落点
### MySQL
- `tasks`
- `static_analysis`
- `dynamic_analysis`
- `analysis_runs`
- `network_requests`
- `master_domains`
- `screenshots`

### MinIO
- APK 原始文件
- 动态截图
- `report.pdf`
- `report_web.html`
- `report_static.html`

## 7. 当前验收口径
一次完整任务应满足：
- 任务状态到 `completed`
- `analysis_runs` 中 `static/dynamic/report` 形成完整阶段记录
- `dynamic_analysis.capture_mode = redroid_zeek`
- `redroid-host-agent /health` 正常，`/slots` 返回 3 个 healthy slot
- `network_requests` 有观测数据
- `master_domains` 有域名统计
- `screenshots` 已落库且图片可访问
- 前端详情页和报告页可正常展示

## 8. 当前已验证成功样本
任务：`00ff992d-95eb-4cdc-b7b9-9d7195a7184a`
- 状态：`completed`
- 截图：`10`
- 观测：`196`
- 域名：`17`
- 唯一 IP：`30`
- capture_mode：`redroid_zeek`

前端页面：
- 详情页：`/tasks/00ff992d-95eb-4cdc-b7b9-9d7195a7184a`
- 报告页：`/reports/00ff992d-95eb-4cdc-b7b9-9d7195a7184a`

## 9. 启停方式
### 本地测试环境推荐
```bash
./scripts/dev_up.sh
./scripts/dev_down.sh
./scripts/dev_restart.sh
```

特点：
- 默认加载项目根目录 `.env`
- API 单进程启动
- API / worker / frontend 均使用最简单的后台进程方式

### 启动
```bash
./scripts/start_services.sh
```

默认启动约定：
- 自动加载项目根目录 `.env`
- API 使用 `tmux` session `intelligent-app-api`
- Worker 使用 `tmux` session `intelligent-app-worker`
- Frontend 使用 `tmux` session `intelligent-app-frontend`
- Frontend 会先执行 `npm run build`，再以 Next.js standalone `server.js` 启动

### 停止
```bash
./scripts/stop_services.sh
```

### 重启
```bash
./scripts/restart_services.sh
```

### 日志
- API：`.runtime_logs/api.log`
- Worker：`.runtime_logs/worker.log`
- 前端：`.runtime_logs/frontend.log`

### 会话检查
```bash
tmux ls
tmux attach -t intelligent-app-api
tmux attach -t intelligent-app-worker
tmux attach -t intelligent-app-frontend
```

### 三节点生产部署
各节点统一使用 `docker compose up -d --build` 初始化部署：

```bash
docker compose -f deploy/frontend/docker-compose.yml up -d --build
docker compose -f deploy/backend/docker-compose.yml up -d --build
docker compose -f deploy/worker/docker-compose.yml up -d --build
```

节点职责：
- `<frontend-node>` 只运行前端，`NEXT_PUBLIC_API_BASE_URL` 指向 `http://<api-node>:8000`
- `<api-node>` 只运行 API
- `<worker-node>` 只运行 Worker

增量发布约定：
- `deploy/backend/docker-compose.yml` 与 `deploy/worker/docker-compose.yml` 均通过 `APP_SOURCE_DIR` 挂载宿主机源码目录到容器 `/app`
- 只改 Python 代码且不新增依赖时，只同步代码到节点源码目录，再执行：

```bash
docker compose -f deploy/backend/docker-compose.yml restart api
docker compose -f deploy/worker/docker-compose.yml restart worker
```

- 仅在新增 pip 依赖、系统依赖或修改 `Dockerfile.backend` 时，才需要重建 backend 镜像

## 10. 最小检查命令
```bash
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/api/v1/frontend/tasks?page=1&page_size=20'
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
```

## 11. 当前明确边界
- 目标是域名、IP、命中次数、时间线和截图，不追求 HTTPS 明文正文
- 详情页和报告页是当前唯一有效展示面
- 不再保留旧方案兼容层
- `redroid-host-agent` 只负责容器管理、抓包、Zeek 和文件回传；不负责 ADB、AI、MySQL、MinIO

## 12. 交接要求
接手此项目时，先读：
1. 本文档 `docs/CURRENT_STATE.md`
2. `docs/CONTEXT_INDEX.md`
3. `deploy/redroid-host-agent/docker-compose.yml`

除此之外，其他历史设计、过程、测试阶段文档都不再作为当前真实状态依据。
