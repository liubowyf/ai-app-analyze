# APK 智能动态分析平台

高并发 APK 智能动态分析与网络监控平台

## 功能特性

- 批量上传 APK 安装包文件
- AI 驱动的动态分析（基于 AutoGLM）
- 流量捕获与白名单过滤
- PDF 格式动态分析报告生成

## 技术栈

- Python 3.10+
- FastAPI
- Celery + Redis
- MySQL
- MinIO
- Open-AutoGLM

## 快速开始

### 环境准备

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填入实际配置
```

3. 启动服务：
```bash
# 启动 API 服务
uvicorn api.main:app --reload

# 启动 Celery Worker
celery -A workers.celery_app worker -l info
```

## 项目结构

```
├── api/                    # API 接口
├── core/                   # 核心配置
├── models/                 # 数据模型
├── modules/                # 功能模块
├── workers/                # Celery 任务
├── tests/                  # 测试用例
└── docs/                   # 文档
```

## 许可证

MIT License
