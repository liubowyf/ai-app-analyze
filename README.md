# 网络反诈中心-智能APP分析平台

一个面向反诈场景的 Android App 自动化分析平台。

当前主线方案基于 **FastAPI + Dramatiq + Next.js + Redroid + tcpdump + Zeek**，支持从页面上传 APK，自动完成静态分析、远端动态分析、网络行为观测、截图采集、结果落库和报告展示。

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
  - 启动 App
  - AI 驱动页面点击、输入、导航和恢复
  - 截图采集
  - UI 结构导出
- 网络观测
  - tcpdump 抓包
  - Zeek 解析
  - 域名、IP、命中次数、时间线统计
- 结果持久化
  - MySQL：结构化分析结果
  - MinIO：截图、报告、APK 文件
- 页面展示
  - 任务列表页
  - 任务详情页
  - 报告页

## 当前主架构

```text
Browser / Frontend (Next.js)
        |
        v
FastAPI API
        |
        v
Dramatiq Worker
        |
        v
Redroid Remote Backend
  |- ADB: install / launch / screencap / uiautomator
  |- SSH: tcpdump / Zeek / artifacts
        |
        v
MySQL + Redis + MinIO
```

## 当前技术栈

- Frontend: Next.js
- API: FastAPI
- Queue: Dramatiq + Redis
- DB: MySQL
- Object Storage: MinIO
- Dynamic Analysis Backend: Redroid Remote
- Traffic Observation: tcpdump + Zeek

## 当前唯一有效方案

本项目当前只保留以下动态分析主线：

- `redroid_remote`
- `tcpdump + Zeek`
- 远端 ADB + SSH

以下方案已移除，不再作为当前架构的一部分：

- Android Docker
- 本地 Android 模拟器池
- MITM / no-mitm / internal proxy 旧链路
- 宿主机 adb reverse 抓包链路
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

按当前实际环境填写：

- MySQL
- Redis
- MinIO
- Redroid 节点
- SSH 凭据

### 3. 启动服务

```bash
./scripts/start_services.sh
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

- Frontend: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`

## 运行流程

1. 页面上传 APK
2. API 创建任务并入队
3. Worker 执行轻量静态分析
4. Worker 调用 `redroid_remote` 进行动态分析
5. 远端 Redroid 完成：
   - 安装
   - 启动
   - AI 探索
   - 截图
   - 抓包
   - Zeek 解析
6. 结果落库到 MySQL
7. 截图和报告写入 MinIO
8. 前端详情页和报告页展示结果

## 结果数据

### MySQL

当前主要表：

- `tasks`
- `static_analysis`
- `dynamic_analysis`
- `analysis_runs`
- `network_requests`
- `master_domains`
- `screenshots`

### MinIO

当前主要对象：

- APK 原始文件
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
- 动态阶段运行记录
- 域名 / IP / 命中统计
- 截图

### 报告页

- App 基本信息
- 权限概览
- Top Domains
- Top IPs
- Observation Hits
- 时间线
- 截图索引

## 配置重点

当前关键配置包括：

- `ANALYSIS_BACKEND=redroid_remote`
- `REDROID_SSH_HOST`
- `REDROID_SSH_PORT`
- `REDROID_SSH_USER`
- `REDROID_SSH_PASSWORD` 或 `REDROID_SSH_KEY_PATH`
- `REDROID_SLOTS_JSON`
- `ADB_INSTALL_TIMEOUT_SECONDS`
- `APP_EXPLORATION_MAX_STEPS`
- `APP_EXPLORATION_TOTAL_ACTION_BUDGET`
- `APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET`

## 最小检查命令

```bash
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/api/v1/frontend/tasks?page=1&page_size=20'
PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py
```

## 测试

后端关键测试：

```bash
pytest -q tests/test_redroid_remote_backend.py tests/test_redroid_traffic_collector.py tests/test_redroid_traffic_parser.py
```

前端测试：

```bash
cd frontend
npm test
npm run build
```

## 目录结构

```text
api/                FastAPI 入口、路由、Schema
core/               配置、数据库、存储
models/             SQLAlchemy 模型
modules/            分析模块、redroid、流量采集、AI 探索
workers/            Dramatiq worker 与任务执行
frontend/           Next.js 前端
tests/              pytest 测试
templates/          报告模板
scripts/            启停与校验脚本
docs/               当前有效文档
```

## 文档入口

优先阅读：

1. [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
2. [`docs/CONTEXT_INDEX.md`](docs/CONTEXT_INDEX.md)
3. [`docs/SERVER_CONNECTION.md`](docs/SERVER_CONNECTION.md)

## 当前边界

本项目当前重点是：

- App 自动化运行
- 域名 / IP / 命中次数 / 时间线统计
- 截图与报告展示

当前不以以下目标为主：

- HTTPS 明文正文
- 完整请求体 / 响应体
- 长期归档与冷存储

## 当前状态

项目当前已验证：

- 页面上传 APK
- 静态分析
- Redroid 远端动态分析
- tcpdump + Zeek 网络观测
- 域名 / IP 落库
- 截图落库
- 详情页与报告页展示

如果接手本项目，先读 [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)。
