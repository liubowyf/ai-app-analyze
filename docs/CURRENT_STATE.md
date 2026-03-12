# 网络反诈中心-智能APP分析平台：当前唯一有效文档

更新时间：2026-03-12

## 1. 当前唯一主线
- 前端：Next.js，主入口 `http://127.0.0.1:3000`
- 后端：FastAPI，主入口 `http://127.0.0.1:8000`
- Worker：Dramatiq
- 动态分析后端：`redroid_remote`
- 动态网络采集：`redroid-1 + tcpdump + Zeek`
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
   - SSH 连接 `<host-agent-node>:22`
   - 安装 APK
   - 启动 App
   - AI 驱动页面探索、点击、输入
   - 截图与 UI 导出
   - 宿主机 `tcpdump` 抓包
   - Zeek 解析 `conn.log / dns.log / ssl.log / http.log`
   - 聚合 `domain / ip / hit_count / source_type`
6. 结果写入 MySQL，截图与报告写入 MinIO
7. 前端详情页和报告页展示结构化结果

## 4. 当前固定基础设施
### 应用服务
- 前端：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8000`

### redroid 分析节点
- ADB：`<host-agent-node>:16555`
- SSH：`<host-agent-node>:22`
- 容器名：`redroid-1`

### 数据与存储
- MySQL：`<host-agent-node>:3306`
- Redis：`<infra-node>:6379`
- MinIO：`<infra-node>:9000`

## 5. 当前环境变量基线
- `ANALYSIS_BACKEND=redroid_remote`
- `REDROID_ADB_SERIAL=<host-agent-node>:16555`
- `REDROID_SSH_HOST=<host-agent-node>`
- `REDROID_SSH_PORT=22`
- `REDROID_SSH_USER=user`
- `REDROID_CONTAINER_NAME=redroid-1`
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
- `network_requests` 有观测数据
- `master_domains` 有域名统计
- `screenshots` 已落库且图片可访问
- 前端详情页和报告页可正常展示

## 8. 当前已验证成功样本
任务：`7a2dbcdc-9eb8-40a6-bbc6-0f4defe8677e`
- 状态：`completed`
- 截图：`7`
- 观测：`2696`
- 域名：`25`
- 唯一 IP：`43`
- capture_mode：`redroid_zeek`

前端页面：
- 详情页：`/tasks/7a2dbcdc-9eb8-40a6-bbc6-0f4defe8677e`
- 报告页：`/reports/7a2dbcdc-9eb8-40a6-bbc6-0f4defe8677e`

## 9. 启停方式
### 启动
```bash
./scripts/start_services.sh
```

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

## 12. 交接要求
接手此项目时，先读：
1. 本文档 `docs/CURRENT_STATE.md`
2. `<ops-connection-doc>`

除此之外，其他历史设计、过程、测试阶段文档都不再作为当前真实状态依据。
