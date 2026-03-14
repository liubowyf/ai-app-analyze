# 智能 APP 分析平台

一个面向反诈场景的 Android 应用自动化分析平台。

当前主线方案基于 **FastAPI + Dramatiq + Next.js + Redroid + tcpdump + Zeek + redroid-host-agent**，支持从页面上传 APK，自动完成静态分析、远端动态分析、网络行为采集、截图与报告生成，并在页面中展示结构化分析结果。

## 项目定位

本项目的重点不是移动应用逆向取证，而是提供一条稳定、可批量、可页面化查看的分析流水线，面向反诈分析输出以下结果：

- 应用基础信息
- 声明权限与运行期权限申请情况
- 动态运行过程截图
- 域名、IP、命中次数、时间线等网络行为统计
- 可直接查看的任务详情页与报告页

## 核心能力

- APK 上传与批量任务创建
- 轻量静态分析
  - 应用名
  - 包名
  - 图标
  - MD5
  - 文件大小
  - 声明权限
  - 启动 Activity 线索
- 基于 Redroid 的远端动态分析
  - 安装 APK
  - 启动应用
  - AI 驱动页面点击、输入、导航与恢复
  - 截图采集
  - UI 结构导出
- 网络行为采集
  - tcpdump 抓包
  - Zeek 解析
  - 域名、IP、命中次数、时间线聚合
- 数据持久化
  - MySQL：结构化分析结果
  - MinIO：图标、截图、报告、原始 APK
- 页面展示
  - 任务列表页
  - 任务详情页
  - 报告页

## 系统架构

```mermaid
flowchart TD
    U[用户 / 浏览器] --> FE[Next.js 前端]
    FE --> API[FastAPI API]
    API --> Q[Dramatiq + Redis]
    Q --> W[Worker]
    W --> SA[静态分析]
    W --> DA[动态分析]

    DA --> RB[Redroid 远端后端]
    RB --> ADB[远程 ADB 控制]
    RB --> HA[redroid-host-agent API]

    ADB --> RR[Redroid 实例]
    HA --> TCP[tcpdump]
    HA --> ZK[Zeek]

    SA --> DB[(MySQL)]
    DA --> DB
    SA --> S3[(MinIO)]
    DA --> S3

    API --> DB
    API --> S3
```

## 运行流程

```mermaid
sequenceDiagram
    participant 浏览器
    participant API
    participant Worker
    participant 静态分析
    participant Redroid
    participant HostAgent
    participant MySQL
    participant MinIO

    浏览器->>API: 上传 APK
    API->>MySQL: 创建任务
    API->>Worker: 入队分析任务
    Worker->>静态分析: 轻量静态分析
    静态分析->>MySQL: 写入静态结果
    静态分析->>MinIO: 上传图标 / APK 产物
    Worker->>Redroid: 安装并启动应用
    Worker->>HostAgent: 启动抓包 / 执行 Zeek / 拉取日志
    Redroid->>Redroid: AI 驱动探索与截图
    Worker->>MySQL: 写入动态结果 / 网络观测 / 域名统计
    Worker->>MinIO: 上传截图 / 报告
    浏览器->>API: 查询任务详情与报告
```

## 技术栈

- 前端：Next.js
- API：FastAPI
- 队列：Dramatiq + Redis
- 数据库：MySQL
- 对象存储：MinIO
- 动态分析后端：Redroid Remote
- 宿主机控制面：redroid-host-agent
- 网络观测：tcpdump + Zeek

## 当前唯一有效方案

当前项目只保留这一条动态分析主线：

- `redroid_remote`
- `远程 ADB + redroid-host-agent`
- `tcpdump + Zeek`

以下历史方案已废弃，不再是当前实现的一部分：

- Android Docker
- 本地 Android 模拟器池
- 旧 MITM / no-mitm / internal proxy 链路
- adb reverse 抓包链路
- 后端 HTML 报告主入口

## 快速开始

### 1. 安装依赖

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

前端依赖：

```bash
cd frontend
npm install
cd ..
```

### 2. 准备环境变量

```bash
cp .env.example .env
```

至少需要正确配置：

- MySQL
- Redis
- MinIO
- Redroid 节点 ADB / host-agent 信息

### 3. 启动服务

本地测试环境推荐：

```bash
./scripts/dev_up.sh
```

停止：

```bash
./scripts/dev_down.sh
```

重启：

```bash
./scripts/dev_restart.sh
```

这套 `dev_*` 脚本特点：

- 默认加载项目根目录 `.env`
- API 使用单进程 `uvicorn`
- 3 个服务全部用最简单的 `nohup + PID 文件` 后台启动
- 适合本机联调和快速自测

如果需要保留会话查看能力，再使用：

```bash
./scripts/start_services.sh
```

默认行为：

- 自动加载项目根目录 `.env`
- 使用 `tmux` 常驻会话托管 API、worker 和 frontend
- 会话名固定为 `intelligent-app-api`、`intelligent-app-worker`、`intelligent-app-frontend`
- 前端会在 `tmux` 会话内执行 `npm run build`，然后以 Next.js standalone `server.js` 方式启动

查看会话：

```bash
tmux ls
tmux attach -t intelligent-app-api
tmux attach -t intelligent-app-worker
tmux attach -t intelligent-app-frontend
```

重启：

```bash
./scripts/restart_services.sh
```

停止：

```bash
./scripts/stop_services.sh
```

### 4. 访问页面

- 前端：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8000`

日志位置：

- API：`.runtime_logs/api.log`
- Worker：`.runtime_logs/worker.log`
- Frontend：`.runtime_logs/frontend.log`

## 配置重点

关键环境变量示例：

| 变量 | 说明 |
|---|---|
| `ANALYSIS_BACKEND` | 动态分析后端，当前固定为 `redroid_remote` |
| `MYSQL_URL` | MySQL 连接串 |
| `REDIS_BROKER_URL` | Dramatiq 使用的 Redis Broker |
| `MINIO_ENDPOINT` | MinIO 地址 |
| `REDROID_HOST_AGENT_BASE_URL` | host-agent 节点 `redroid-host-agent` 地址 |
| `REDROID_HOST_AGENT_TOKEN` | `redroid-host-agent` 鉴权 token |
| `REDROID_SLOTS_JSON` | 可用的 Redroid 槽位定义 |
| `ADB_INSTALL_TIMEOUT_SECONDS` | APK 安装超时 |
| `APP_EXPLORATION_MAX_STEPS` | 单轮探索步数上限 |
| `APP_EXPLORATION_TOTAL_ACTION_BUDGET` | 全局操作预算 |
| `APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET` | 全局截图预算 |

说明：
- [`.env.example`](/Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统/.env.example) 只保留配置项和占位值
- 真实部署依赖、真实地址和密钥只应放在本地 [`.env`](/Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统/.env)

## 三节点生产部署

生产环境按固定节点拆分：

- `<frontend-node>`：`frontend`
- `<api-node>`：`api`
- `<worker-node>`：`worker`

调度链路：

- 用户 -> `frontend`
- `frontend` -> `api`
- `api` -> MySQL / Redis / MinIO
- `worker` -> Redis / MySQL / MinIO / AI / `redroid-host-agent`

各节点部署命令：

```bash
docker compose -f deploy/frontend/docker-compose.yml up -d --build
docker compose -f deploy/backend/docker-compose.yml up -d --build
docker compose -f deploy/worker/docker-compose.yml up -d --build
```

后端增量发布约定：

- `api` 与 `worker` 容器会把 `${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}` 挂载到容器内 `/app`
- 只改 Python 代码且不新增依赖时，不需要重打 backend 镜像
- 只需把变更文件同步到目标节点源码目录，然后重启对应服务

```bash
rsync -av api/ core/ models/ modules/ workers/ devops@<api-node>:/home/devops/ai-app-analyze/
docker compose -f deploy/backend/docker-compose.yml restart api

rsync -av core/ models/ modules/ workers/ devops@<worker-node>:/home/devops/ai-app-analyze/
docker compose -f deploy/worker/docker-compose.yml restart worker
```

节点本地 `.env` 约定：

- `deploy/frontend/.env`
  - `NEXT_PUBLIC_API_BASE_URL=http://<api-node>:8000`
- `deploy/backend/.env`
  - `APP_SOURCE_DIR=/home/devops/ai-app-analyze`
  - MySQL / Redis / MinIO / `API_TOKEN`
  - `REDROID_HOST_AGENT_BASE_URL`
  - `REDROID_SLOTS_JSON`
- `deploy/worker/.env`
  - `APP_SOURCE_DIR=/home/devops/ai-app-analyze`
  - MySQL / Redis / MinIO / AI
  - `REDROID_HOST_AGENT_BASE_URL`
  - `REDROID_SLOTS_JSON`

建议上线顺序：

1. `api`
2. `worker`
3. `frontend`

上线后最小检查：

```bash
curl -fsS http://<api-node>:8000/health
curl -fsS http://<api-node>:8000/api/v1/frontend/runtime-status
curl -I http://<frontend-node>:3000
```

## 数据存储

### MySQL

主要表：

- `tasks`
- `static_analysis`
- `dynamic_analysis`
- `analysis_runs`
- `network_requests`
- `master_domains`
- `screenshots`

### MinIO

主要对象：

- 原始 APK
- 应用图标
- 动态截图
- `report.pdf`
- `report_web.html`
- `report_static.html`

## 页面能力

### 任务列表页

- 任务状态
- 应用名 / 包名
- APK 文件名
- 风险等级
- 时间信息

### 任务详情页

- 静态分析信息
- 权限信息
- 阶段运行记录
- 域名 / IP / 命中统计
- 截图

### 报告页

- 应用基础信息
- 权限概览
- Top Domains
- Top IPs
- Observation Hits
- 时间线
- 截图索引

## 验证命令

健康检查：

```bash
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/api/v1/frontend/tasks?page=1&page_size=20'
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
```

后端关键测试：

```bash
pytest -q \
  tests/test_redroid_remote_backend.py \
  tests/test_redroid_traffic_collector.py \
  tests/test_redroid_traffic_parser.py
```

前端测试：

```bash
cd frontend
npm test
npm run build
```

## 仓库结构

```text
api/                FastAPI 入口、路由、Schema
core/               配置、数据库、存储
models/             SQLAlchemy 模型
modules/            分析模块、Redroid、流量采集、AI 探索
workers/            Dramatiq Worker 与任务执行
frontend/           Next.js 前端
tests/              pytest 测试
templates/          报告模板
scripts/            启停与校验脚本
```

## 当前状态

项目当前已经验证：

- 页面上传 APK
- 轻量静态分析
- Redroid 远端动态分析
- tcpdump + Zeek 网络观测
- 域名 / IP 统计落库
- 截图落库
- 详情页与报告页展示

## 当前边界

当前方案重点解决的是：

- 动态运行
- 域名 / IP / 命中次数 / 时间线统计
- 截图与报告展示

当前不以以下能力为目标：

- HTTPS 明文正文
- 完整请求体 / 响应体
- 深度移动逆向取证能力



## 许可证

本项目采用 **Apache License 2.0** 开源许可证。详见根目录下的 `LICENSE` 文件。
