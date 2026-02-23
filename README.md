# APK 智能动态分析平台

一套智能化的 APK 动态分析系统，通过 AI 驱动的方式模拟真实用户行为，诱导 APP 暴露核心逻辑，精准识别潜在的恶意行为和 C2 通信特征。

## 核心特性

- **自动化分析** - 批量上传 APK，全自动完成静态分析 + 动态运行 + 流量捕获
- **AI 驱动交互** - 集成 AutoGLM-Phone，模拟真实用户点击、滑动、输入等行为
- **精准威胁识别** - 主控域名分析器识别 C2 服务器，网络白名单过滤噪声
- **专业报告输出** - 生成包含截图和网络行为分析的 PDF 动态分析报告

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  API 网关   │────→│ 任务调度    │────→│  执行层     │
│  (FastAPI)  │     │  (Celery)   │     │  (分析模块) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   MySQL     │     │  RabbitMQ   │     │   MinIO     │
│  (元数据)   │     │  (队列)     │     │ (文件存储)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 核心模块

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| APK Analyzer | 静态分析 | androguard |
| Android Runner | 模拟器控制 | ADB |
| Traffic Monitor | 流量捕获 | mitmproxy |
| AI Driver | 智能决策 | AutoGLM-Phone |
| Screenshot Manager | 截图去重 | Pillow + imagehash |
| App Explorer | 4阶段探索 | 混合策略 |
| Domain Analyzer | 主控域名识别 | 多因子评分 |
| Report Generator | PDF 报告 | WeasyPrint |

## 快速开始

### 环境要求

- Python 3.11+
- MySQL 8.0+
- RabbitMQ 3.x+
- MinIO

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd 智能APP分析系统

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件:

```env
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=apk_analysis

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Celery
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=rpc://

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key

# AI Service
AI_BASE_URL=http://localhost:6000/v1
AI_MODEL_NAME=autoglm-phone-9b
```

### 启动服务

```bash
# 1. 初始化数据库 (首次运行)
source venv/bin/activate
python init_db.py

# 2. 启动 API 服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动 Celery Worker
celery -A workers.celery_app worker -l info -Q default,static,dynamic,report
```

> 详细操作请参考 [运维指南](docs/OPERATIONS.md)

### API 使用

```bash
# 上传 APK
curl -X POST "http://localhost:8000/api/v1/apk/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.apk"

# 开始分析
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "your-task-id"}'

# 查询状态
curl "http://localhost:8000/api/v1/tasks/your-task-id"

# 下载报告
curl "http://localhost:8000/api/v1/tasks/your-task-id/report" -o report.pdf
```

## 项目结构

```
├── api/                    # API 网关
│   ├── main.py            # FastAPI 入口
│   ├── routers/           # 路由模块
│   └── schemas/           # 数据模型
├── core/                   # 核心模块
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库连接
│   └── storage.py         # MinIO 封装
├── workers/                # Celery 任务
│   ├── celery_app.py      # Celery 配置
│   ├── static_analyzer.py # 静态分析任务
│   ├── dynamic_analyzer.py# 动态分析任务
│   └── report_generator.py# 报告生成任务
├── modules/                # 功能模块
│   ├── apk_analyzer/      # APK 静态分析
│   ├── android_runner/    # 模拟器控制
│   ├── traffic_monitor/   # 流量监控
│   ├── ai_driver/         # AI 驱动
│   ├── screenshot_manager/# 截图管理
│   ├── exploration_strategy/# 应用探索
│   ├── domain_analyzer/   # 域名分析
│   └── report_generator/  # 报告生成
├── models/                 # 数据库模型
├── templates/              # 报告模板
├── tests/                  # 测试用例
└── docs/                   # 文档
    ├── PRD.md             # 产品需求文档
    └── ARCHITECTURE.md    # 系统架构文档
```

## 文档

- [产品需求文档 (PRD)](docs/PRD.md) - 完整的产品需求和功能说明
- [系统架构文档 (ARCHITECTURE)](docs/ARCHITECTURE.md) - 技术架构和实现细节
- [运维指南 (OPERATIONS)](docs/OPERATIONS.md) - 环境配置、服务启动、问题排查
- [测试指南 (TESTING)](docs/TESTING.md) - 测试框架、测试结构、运行方法

## 分析流程

```
上传 APK
    │
    ▼
静态分析 (提取包名、权限、组件)
    │
    ▼
动态分析
    ├── 连接模拟器
    ├── 安装 APK
    ├── 启动流量监控
    ├── AI 智能探索 (4阶段)
    │   ├── Phase 1: 基础设置
    │   ├── Phase 2: 导航探索
    │   ├── Phase 3: 自主探索
    │   └── Phase 4: 场景测试
    └── 截图捕获去重
    │
    ▼
主控域名分析
    │
    ▼
生成 PDF 报告
```

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| 任务队列 | Celery + RabbitMQ |
| 数据库 | MySQL + SQLAlchemy |
| 对象存储 | MinIO |
| 静态分析 | androguard |
| 流量代理 | mitmproxy |
| AI 模型 | AutoGLM-Phone-9B |
| PDF 生成 | WeasyPrint |
| 图像处理 | Pillow + imagehash |

## 许可证

MIT License
