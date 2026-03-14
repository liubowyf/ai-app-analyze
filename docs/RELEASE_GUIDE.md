# 发版指南

本文档只描述当前生产环境有效的发版方式。

当前前端正式展示面：

- 任务列表页 `/`
- 报告页 `/reports/{taskId}`

说明：

- `/tasks/{taskId}` 仅保留兼容跳转，不再作为正式页面
- 报告页权限数据依赖 `analysis_runs.details.permission_summary`
- Android 权限中文释义依赖仓库内码表 `data/android_permission_catalog.json`

## 1. 节点角色

- `<frontend-node>`：`frontend`
- `<api-node>`：`api`
- `<worker-node>`：`worker`
- `<host-agent-node>`：`redroid-host-agent`

生产链路：

- 用户 -> `frontend`
- `frontend` -> `api`
- `api` -> MySQL / Redis / MinIO
- `worker` -> Redis / MySQL / MinIO / AI / `redroid-host-agent`

## 1.1 服务器连接方式

内网三节点当前通过公网跳板机反向隧道访问，推荐直接使用以下连接命令：

```bash
ssh -p <frontend-port> devops@<jump-host>   # frontend
ssh -p <api-port> devops@<jump-host>   # api
ssh -p <worker-port> devops@<jump-host>   # worker
```

如果本机已配置 `~/.ssh/config`，可直接使用：

```bash
ssh <frontend-alias>   # frontend
ssh <api-alias>   # api
ssh <worker-alias>   # worker
```

注意：

- 仓库文档不记录服务器密码
- 当前连接口令和完整连接维护信息统一保存在外部运维文档：
  - `<ops-connection-doc>`
- 生产发版前，如发现隧道不可用，先检查各节点 `ssh-tunnel.service`

## 2. 发版分级

### 2.1 代码增量发布

适用场景：

- 只改 Python 代码
- 不新增 pip 依赖
- 不改系统依赖
- 不改 `Dockerfile.backend`

当前约定：

- `deploy/backend/docker-compose.yml` 和 `deploy/worker/docker-compose.yml` 会将 `${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}` 挂载到容器内 `/app`
- 因此 `api` 和 `worker` 可以只同步源码后重启服务

推荐命令：

```bash
rsync -av api/ core/ models/ modules/ workers/ devops@<api-node>:/home/devops/ai-app-analyze/
docker compose -f deploy/backend/docker-compose.yml restart api

rsync -av core/ models/ modules/ workers/ devops@<worker-node>:/home/devops/ai-app-analyze/
docker compose -f deploy/worker/docker-compose.yml restart worker
```

### 2.2 依赖补丁发布

适用场景：

- 新增单个或少量 pip 依赖
- 不需要重建完整 backend 大镜像

推荐方式：

- 只传新增 wheel 或小补丁文件
- 在目标节点基于当前 backend 镜像生成一个新 tag
- 更新 `deploy/backend/docker-compose.yml` / `deploy/worker/docker-compose.yml` 的镜像 tag
- 重启服务

适合类似：

- `redis` Python 包缺失
- 少量纯 Python 依赖修复

### 2.3 完整镜像发布

适用场景：

- 修改 `Dockerfile.backend`
- 修改系统依赖
- 修改基础镜像
- 修改前端构建产物
- 修改需要重新 `npm build` 的内容

这时才需要重新 build 并分发完整镜像。

## 3. 当前生产初始化部署

初始化或大版本升级时使用：

```bash
docker compose -f deploy/frontend/docker-compose.yml up -d --build
docker compose -f deploy/backend/docker-compose.yml up -d --build
docker compose -f deploy/worker/docker-compose.yml up -d --build
```

## 4. 节点环境变量

### 4.1 frontend

文件：

- `deploy/frontend/.env`

关键项：

- `NEXT_PUBLIC_API_BASE_URL=http://<api-node>:8000`

### 4.2 api

文件：

- `deploy/backend/.env`

关键项：

- `APP_SOURCE_DIR=/home/devops/ai-app-analyze`
- `MYSQL_*`
- `REDIS_BROKER_URL`
- `MINIO_*`
- `API_TOKEN`
- `REDROID_HOST_AGENT_BASE_URL`
- `REDROID_HOST_AGENT_TOKEN`
- `REDROID_SLOTS_JSON`

### 4.3 worker

文件：

- `deploy/worker/.env`

关键项：

- `APP_SOURCE_DIR=/home/devops/ai-app-analyze`
- `MYSQL_*`
- `REDIS_BROKER_URL`
- `MINIO_*`
- `AI_*`
- `API_TOKEN`
- `REDROID_HOST_AGENT_BASE_URL`
- `REDROID_HOST_AGENT_TOKEN`
- `REDROID_SLOTS_JSON`

## 5. 发布顺序

### 5.1 代码增量发布

1. 同步 `api` 代码
2. `restart api`
3. 同步 `worker` 代码
4. `restart worker`
5. 前端如无改动，不需要处理

### 5.2 完整版本发布

1. `api`
2. `worker`
3. `frontend`

## 6. 最小验证

### 6.1 API

```bash
curl -fsS http://<api-node>:8000/health
curl -fsS http://<api-node>:8000/api/v1/frontend/runtime-status
```

期望：

- `api_healthy=true`
- `worker_ready=true`
- `redroid.healthy_slots=3`

### 6.2 Frontend

```bash
curl -I http://<frontend-node>:3001
```

### 6.3 Worker

查看容器日志，确认没有依赖缺失或 broker 初始化失败：

```bash
docker logs --tail 100 apk-analysis-worker
```

## 7. 回滚

如果代码增量发布后异常：

1. 回滚节点源码目录到上一版
2. 重启对应容器

如果完整镜像发布后异常：

1. 将 compose 镜像 tag 切回上一版
2. 执行 `docker compose up -d --no-build`

## 8. 当前建议

- 优先使用“代码增量发布”
- 只有依赖或系统环境变更，才走补丁层或完整镜像发布
- 前端仍建议按镜像发布，不建议直接在生产节点热替换 Next 构建产物
