#!/bin/bash
# Celery Worker 启动脚本

# 激活虚拟环境
source venv/bin/activate

# 停止已有的 Worker
echo "停止已有的 Celery Worker..."
pkill -f "celery.*worker" 2>/dev/null
sleep 2

# 启动 Worker (监听所有队列)
echo "启动 Celery Worker..."
echo "监听队列: default, static, dynamic, report"
echo "日志级别: info"
echo "日志文件: /tmp/celery_worker.log"
echo ""

celery -A workers.celery_app worker \
    -Q default,static,dynamic,report \
    --loglevel=info \
    > /tmp/celery_worker.log 2>&1 &

WORKER_PID=$!
echo "Worker 已启动 (PID: $WORKER_PID)"
echo ""
echo "查看日志:"
echo "  tail -f /tmp/celery_worker.log"
echo ""
echo "停止 Worker:"
echo "  pkill -f 'celery.*worker'"
