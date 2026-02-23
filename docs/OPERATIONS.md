# 运维指南

本文档包含 APK 智能动态分析平台的运维操作指南,涵盖数据库初始化、服务启动、Android 模拟器配置等常见操作。

---

## 目录

- [环境准备](#环境准备)
- [数据库初始化](#数据库初始化)
- [服务启动](#服务启动)
- [Android 模拟器配置](#android-模拟器配置)
- [网络诊断](#网络诊断)
- [常见问题](#常见问题)

---

## 环境准备

### 系统要求

- Python 3.11+
- MySQL 8.0+
- RabbitMQ 3.x+
- MinIO
- Docker (用于 Android 模拟器)

### 依赖安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

---

## 数据库初始化

### 自动初始化

使用 Python 脚本初始化数据库表结构:

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行初始化脚本
python init_db.py
```

**脚本功能**:
- 创建所有数据库表 (tasks, whitelist_rules 等)
- 自动检测并报告创建结果
- 错误处理和状态反馈

**预期输出**:
```
Creating database tables...
✅ Database tables created successfully!

Created tables:
  - tasks
  - whitelist_rules
```

### 手动初始化

如需手动创建表,可使用以下 Python 代码:

```python
from core.database import engine, Base
from models.task import Task
from models.whitelist import WhitelistRule

# 创建所有表
Base.metadata.create_all(bind=engine)
```

---

## 服务启动

### API 服务

```bash
# 开发模式
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Celery Worker

#### 启动命令

```bash
# 前台运行 (推荐调试时使用)
celery -A workers.celery_app worker \
    -Q default,static,dynamic,report \
    --loglevel=info

# 后台运行
celery -A workers.celery_app worker \
    -Q default,static,dynamic,report \
    --loglevel=info \
    > /tmp/celery_worker.log 2>&1 &

# 查看日志
tail -f /tmp/celery_worker.log
```

#### 队列说明

| 队列 | 用途 |
|------|------|
| `default` | 默认队列,处理通用任务 |
| `static` | 静态分析任务 |
| `dynamic` | 动态分析任务 |
| `report` | 报告生成任务 |

#### 停止 Worker

```bash
# 查找 Worker 进程
ps aux | grep "celery.*worker"

# 停止所有 Worker
pkill -f "celery.*worker"

# 停止指定 PID
kill <PID>
```

### MinIO 服务

```bash
# 启动 MinIO
minio server /data --console-address ":9001"

# 后台运行
nohup minio server /data --console-address ":9001" > /tmp/minio.log 2>&1 &
```

---

## Android 模拟器配置

### 模拟器列表配置

系统使用 Docker 容器运行 Android 模拟器,推荐配置如下:

| 容器名称 | ADB 端口 | noVNC 端口 | mitmproxy 端口 |
|---------|---------|-----------|---------------|
| android-emulator-1 | 5555 | 6080 | 9080 |
| android-emulator-2 | 5556 | 6081 | 9081 |
| android-emulator-3 | 5557 | 6082 | 9082 |
| android-emulator-4 | 5558 | 6083 | 9083 |

### 创建模拟器容器

使用 Docker 命令创建模拟器容器:

```bash
# 代理配置
PROXY_HOST="10.16.150.4"
PROXY_PORT="3128"

# 创建单个模拟器容器
docker run -d \
  --name android-emulator-1 \
  --privileged \
  -p 5555:5555 \
  -p 6080:6080 \
  -p 9080:8080 \
  -e HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}" \
  -e HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}" \
  -e http_proxy="http://${PROXY_HOST}:${PROXY_PORT}" \
  -e https_proxy="http://${PROXY_HOST}:${PROXY_PORT}" \
  -e NO_PROXY="localhost,127.0.0.1,10.16.0.0/16" \
  -e no_proxy="localhost,127.0.0.1,10.16.0.0/16" \
  -e EMULATOR_DEVICE="Nexus 5" \
  -e WEB_VNC="true" \
  --memory="4g" \
  -v /dev/kvm:/dev/kvm \
  budtmo/docker-android:emulator_11.0
```

**参数说明**:
- `--privileged`: 特权模式,模拟器需要
- `-p 5555:5555`: ADB 端口映射
- `-p 6080:6080`: noVNC Web 端口
- `-p 9080:8080`: mitmproxy 代理端口
- `-e HTTP_PROXY`: HTTP 代理配置
- `-e EMULATOR_DEVICE`: 模拟设备型号
- `-e WEB_VNC`: 启用 Web VNC
- `--memory="4g"`: 内存限制
- `-v /dev/kvm:/dev/kvm`: KVM 加速 (提升性能)

### 批量创建模拟器

```bash
# 定义容器配置
CONTAINERS=(
  "android-emulator-1 5555 6080 9080"
  "android-emulator-2 5556 6081 9081"
  "android-emulator-3 5557 6082 9082"
  "android-emulator-4 5558 6083 9083"
)

# 循环创建
for container_info in "${CONTAINERS[@]}"; do
  read -r name adb_port novnc_port mitm_port <<< "$container_info"

  docker run -d \
    --name "${name}" \
    --privileged \
    -p ${adb_port}:5555 \
    -p ${novnc_port}:6080 \
    -p ${mitm_port}:8080 \
    -e HTTP_PROXY="http://10.16.150.4:3128" \
    -e HTTPS_PROXY="http://10.16.150.4:3128" \
    -e http_proxy="http://10.16.150.4:3128" \
    -e https_proxy="http://10.16.150.4:3128" \
    -e NO_PROXY="localhost,127.0.0.1,10.16.0.0/16" \
    -e no_proxy="localhost,127.0.0.1,10.16.0.0/16" \
    -e EMULATOR_DEVICE="Nexus 5" \
    -e WEB_VNC="true" \
    --memory="4g" \
    -v /dev/kvm:/dev/kvm \
    budtmo/docker-android:emulator_11.0
done
```

### 连接到模拟器

```bash
# 连接 ADB
adb connect 10.16.148.66:5555

# 查看已连接设备
adb devices

# 通过 noVNC 访问 (浏览器打开)
http://10.16.148.66:6080
```

### 配置模拟器代理

为已运行的模拟器配置 HTTP 代理:

```bash
# 代理服务器
PROXY_HOST="10.16.150.4"
PROXY_PORT="3128"

# 模拟器列表
EMULATORS=(
  "10.16.148.66:5555"
  "10.16.148.66:5556"
  "10.16.148.66:5557"
  "10.16.148.66:5558"
)

# 连接并配置代理
for emulator in "${EMULATORS[@]}"; do
  echo "配置 ${emulator}..."
  adb connect "${emulator}"
  adb -s "${emulator}" shell settings put global http_proxy "${PROXY_HOST}:${PROXY_PORT}"
done

# 验证配置
for emulator in "${EMULATORS[@]}"; do
  proxy=$(adb -s "${emulator}" shell settings get global http_proxy | tr -d '\r')
  echo "${emulator}: ${proxy}"
done
```

### 停止和删除容器

```bash
# 停止单个容器
docker stop android-emulator-1

# 删除单个容器
docker rm android-emulator-1

# 停止所有模拟器容器
docker stop $(docker ps -q --filter "name=android-emulator")

# 删除所有模拟器容器
docker rm $(docker ps -aq --filter "name=android-emulator")
```

---

## 网络诊断

### 检查宿主机代理

```bash
# 测试代理连接
curl --proxy http://10.16.150.4:3128 -I https://www.google.com

# 预期输出: HTTP/2 200
```

### 检查容器状态

```bash
# 查看容器列表
docker ps | grep android-emulator

# 查看容器详细信息
docker inspect android-emulator-1
```

### 检查容器网络配置

```bash
# 查看容器环境变量
docker exec android-emulator-1 env | grep -i proxy

# 查看容器网络接口
docker exec android-emulator-1 ip addr show

# 查看容器 DNS 配置
docker exec android-emulator-1 cat /etc/resolv.conf
```

### 测试容器网络连接

```bash
# 测试容器内直接访问
docker exec android-emulator-1 ping -c 2 google.com

# 测试容器内通过代理访问
docker exec android-emulator-1 curl -v --proxy http://10.16.150.4:3128 https://www.google.com

# 测试内网连接
docker exec android-emulator-1 ping -c 2 10.16.150.4
```

### 完整诊断流程

```bash
# 1. 测试宿主机代理
curl --proxy http://10.16.150.4:3128 -I https://www.google.com --connect-timeout 10

# 2. 检查容器状态
docker ps | grep android-emulator

# 3. 检查容器环境变量
docker exec android-emulator-1 env | grep -i proxy

# 4. 测试容器网络
docker exec android-emulator-1 ping -c 2 google.com

# 5. 测试代理访问
docker exec android-emulator-1 curl -I --proxy http://10.16.150.4:3128 https://www.google.com

# 6. 检查容器 IP
docker exec android-emulator-1 ip addr show

# 7. 检查 DNS
docker exec android-emulator-1 cat /etc/resolv.conf

# 8. 测试内网连接
docker exec android-emulator-1 ping -c 2 10.16.150.4
```

---

## 常见问题

### 1. 数据库连接失败

**错误**: `Can't connect to MySQL server`

**解决方案**:
```bash
# 检查 MySQL 服务
systemctl status mysql

# 检查连接配置
cat .env | grep MYSQL

# 测试连接
mysql -h ${MYSQL_HOST} -P ${MYSQL_PORT} -u ${MYSQL_USER} -p
```

### 2. Celery Worker 无法接收任务

**错误**: 任务一直处于 pending 状态

**解决方案**:
```bash
# 检查 Worker 是否运行
ps aux | grep "celery.*worker"

# 检查队列配置
celery -A workers.celery_app inspect active_queues

# 重启 Worker
pkill -f "celery.*worker"
celery -A workers.celery_app worker -Q default,static,dynamic,report --loglevel=info
```

### 3. Android 模拟器无法启动

**错误**: 容器启动失败或模拟器卡住

**解决方案**:
```bash
# 检查 KVM 支持
ls -l /dev/kvm

# 检查容器日志
docker logs android-emulator-1

# 重启容器
docker restart android-emulator-1

# 查看容器资源使用
docker stats android-emulator-1
```

### 4. 网络代理不生效

**错误**: 容器无法访问互联网

**解决方案**:
```bash
# 1. 测试宿主机代理
curl --proxy http://10.16.150.4:3128 -I https://www.google.com

# 2. 重新配置容器代理环境变量
docker exec android-emulator-1 bash -c "export HTTP_PROXY=http://10.16.150.4:3128"

# 3. 配置模拟器代理
adb -s 10.16.148.66:5555 shell settings put global http_proxy 10.16.150.4:3128

# 4. 验证代理配置
adb -s 10.16.148.66:5555 shell settings get global http_proxy
```

### 5. MinIO 连接失败

**错误**: `Connection refused` 或 `Access denied`

**解决方案**:
```bash
# 检查 MinIO 服务
systemctl status minio

# 检查端口
netstat -tulpn | grep 9000

# 测试连接
curl http://localhost:9000/minio/health/live

# 检查访问密钥
cat .env | grep MINIO
```

### 6. ADB 连接失败

**错误**: `unable to connect to 10.16.148.66:5555`

**解决方案**:
```bash
# 重启 ADB 服务
adb kill-server
adb start-server

# 重新连接
adb connect 10.16.148.66:5555

# 检查设备列表
adb devices
```

---

## 性能优化建议

### 1. 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_task_status ON tasks(status);
CREATE INDEX idx_task_created_at ON tasks(created_at);

-- 配置连接池 (在 .env 中)
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

### 2. Celery 优化

```bash
# 启动多个 Worker 进程
celery -A workers.celery_app worker \
    -Q default,static,dynamic,report \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=100
```

### 3. Docker 优化

```bash
# 清理未使用资源
docker system prune -a

# 限制容器日志大小
docker run ... --log-opt max-size=10m --log-opt max-file=3
```

---

## 监控和日志

### 查看服务日志

```bash
# API 日志
tail -f /var/log/apk-analysis/api.log

# Celery Worker 日志
tail -f /tmp/celery_worker.log

# MinIO 日志
tail -f /tmp/minio.log

# Docker 容器日志
docker logs -f android-emulator-1
```

### 监控资源使用

```bash
# 系统资源
htop

# Docker 资源
docker stats

# MySQL 连接
mysqladmin -u root -p processlist
```

---

## 备份和恢复

### 数据库备份

```bash
# 备份
mysqldump -h ${MYSQL_HOST} -u ${MYSQL_USER} -p ${MYSQL_DATABASE} > backup_$(date +%Y%m%d).sql

# 恢复
mysql -h ${MYSQL_HOST} -u ${MYSQL_USER} -p ${MYSQL_DATABASE} < backup_20260220.sql
```

### MinIO 备份

```bash
# 使用 MinIO Client (mc)
mc mirror local-minio /backup/minio

# 或直接备份数据目录
tar -czf minio_backup_$(date +%Y%m%d).tar.gz /data/minio
```

---

**最后更新**: 2026-02-20
