# APK 智能动态分析平台 - 产品需求文档 (PRD)

> **版本**: v2.0
> **日期**: 2026-02-20
> **状态**: 已实现

---

## 一、项目概述与目标

### 1.1 项目背景

随着移动互联网的快速发展，涉诈 APP 层出不穷，传统静态分析手段已难以应对加壳、混淆、动态加载等对抗技术。本平台旨在构建一套**智能化的 APK 动态分析系统**，通过 AI 驱动的方式模拟真实用户行为，诱导 APP 暴露核心逻辑，从而精准识别潜在的恶意行为和 C2 通信特征。

### 1.2 核心目标

| 目标 | 描述 | 实现状态 |
|------|------|----------|
| **自动化分析** | 支持批量上传 APK，全自动完成静态分析 + 动态运行 + 流量捕获 | ✅ 已实现 |
| **AI 驱动交互** | 集成 AutoGLM-Phone，模拟真实用户点击、滑动、输入等行为 | ✅ 已实现 |
| **精准威胁识别** | 通过网络白名单机制和主控域名分析，精准锁定涉诈 C2 域名/IP | ✅ 已实现 |
| **专业报告输出** | 生成包含截图和网络行为分析的 PDF 动态分析报告 | ✅ 已实现 |

### 1.3 系统边界

```
┌─────────────────────────────────────────────────────────────────┐
│                        系统边界                                   │
├─────────────────────────────────────────────────────────────────┤
│  输入：APK 安装包文件（批量上传）                                   │
│  输出：PDF 动态分析报告 + 结构化分析数据                            │
│  接口：RESTful API（供外部平台调用）                                │
│  环境：x86 服务器 + Android 模拟器集群 + AI 服务                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、平台系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            API 层                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Gateway                               │   │
│  │         /api/v1/apk/upload | /api/v1/tasks | /api/v1/whitelist  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           调度层                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │  Celery Worker  │  │  Celery Worker  │  │  Celery Worker  │        │
│  │  (static queue) │  │ (dynamic queue) │  │ (report queue)  │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           执行层                                         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────┐ │
│  │  APK Analyzer │ │ Android Runner│ │Traffic Monitor│ │ AI Driver  │ │
│  │  (静态分析)    │ │ (模拟器控制)   │ │ (流量捕获)    │ │(智能决策)  │ │
│  └───────────────┘ └───────────────┘ └───────────────┘ └────────────┘ │
│                                                                         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────┐ │
│  │ Screenshot Mgr│ │ App Explorer  │ │ Domain Analyzer│ │Report Gen │ │
│  │ (截图管理)    │ │ (应用探索)    │ │ (主控域名)     │ │(报告生成) │ │
│  └───────────────┘ └───────────────┘ └───────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           存储层                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │   MySQL 8.0     │  │   Redis 7.0     │  │     MinIO       │        │
│  │  (元数据存储)   │  │  (队列/缓存)    │  │ (APK/截图/报告) │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心数据流

```
用户上传 APK
    │
    ▼
┌─────────────────┐
│  静态分析任务   │ ──→ 提取包名、权限、组件、签名等信息
└─────────────────┘
    │
    ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  连接模拟器     │ ──→ │  安装 APK       │ ──→ │  启动流量监控   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
    │                                                    │
    ▼                                                    ▼
┌─────────────────┐                              ┌─────────────────┐
│  AI 智能探索    │ ←── AI 分析截图决策 ──→      │  网络流量捕获   │
│  (4 阶段混合)   │                              │  (mitmproxy)   │
└─────────────────┘                              └─────────────────┘
    │                                                    │
    ▼                                                    ▼
┌─────────────────┐                              ┌─────────────────┐
│  截图捕获去重   │                              │  主控域名分析   │
└─────────────────┘                              └─────────────────┘
    │                                                    │
    └──────────────────────┬─────────────────────────────┘
                           ▼
                    ┌─────────────────┐
                    │   生成 PDF 报告 │
                    └─────────────────┘
```

---

## 三、核心功能模块

### 3.1 模块清单

| 模块编号 | 模块名称 | 职责描述 | 实现状态 |
|----------|----------|----------|----------|
| M01 | API Gateway | RESTful 接口服务 | ✅ 已实现 |
| M02 | Task Scheduler | Celery 任务调度管理 | ✅ 已实现 |
| M03 | Storage Manager | MinIO 对象存储封装 | ✅ 已实现 |
| M04 | APK Analyzer | 静态分析引擎 | ✅ 已实现 |
| M05 | Android Runner | Android 模拟器管理 | ✅ 已实现 |
| M06 | Traffic Monitor | mitmproxy 流量捕获 | ✅ 已实现 |
| M07 | AI Driver | AutoGLM-Phone 集成 | ✅ 已实现 |
| M08 | Screenshot Manager | 截图捕获与去重 | ✅ 已实现 |
| M09 | App Explorer | 4 阶段混合探索策略 | ✅ 已实现 |
| M10 | Domain Analyzer | 主控域名分析器 | ✅ 已实现 |
| M11 | Report Generator | PDF 报告生成 | ✅ 已实现 |

### 3.2 模块详细设计

#### M01 - API Gateway

**职责**：提供统一的 RESTful API 入口

**接口清单**：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/apk/upload` | 上传 APK 文件 |
| POST | `/api/v1/tasks` | 创建分析任务 |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态 |
| POST | `/api/v1/tasks/{task_id}/retry` | 重试失败任务 |
| GET | `/api/v1/tasks/{task_id}/report` | 下载 PDF 报告 |
| GET | `/api/v1/tasks` | 任务列表（分页/筛选） |
| GET | `/api/v1/whitelist` | 获取白名单列表 |
| POST | `/api/v1/whitelist` | 添加白名单规则 |
| PUT | `/api/v1/whitelist/{id}` | 更新白名单规则 |
| DELETE | `/api/v1/whitelist/{id}` | 删除白名单规则 |

**技术栈**：FastAPI + Pydantic + Uvicorn

---

#### M02 - Task Scheduler

**职责**：任务队列管理、状态流转、失败重试

**任务状态机**：

```
pending ──→ queued ──→ static_analyzing ──→ dynamic_analyzing ──→ report_generating ──→ completed
    │           │              │                   │                      │
    └───────────┴──────────────┴───────────────────┴──────────────────────┴──→ failed
                                                                                   │
                                                                                   ↓
                                                                               retry
```

**任务优先级**：
- urgent：紧急分析（VIP 任务）
- normal：普通分析
- batch：批量分析

**技术栈**：Celery + Redis

---

#### M03 - Storage Manager

**职责**：MinIO 对象存储的统一封装

**存储结构**：

```
bucket: apk-analysis
├── apks/                    # APK 文件存储
│   └── {task_id}/
│       └── {md5}.apk
├── screenshots/             # 运行截图存储
│   └── {task_id}/
│       ├── install.png
│       ├── launch.png
│       └── explore_*.png
└── reports/                 # PDF 报告存储
    └── {task_id}/
        └── report.pdf
```

---

#### M04 - APK Analyzer

**职责**：APK 静态分析

**分析内容**：

| 类别 | 分析项 |
|------|--------|
| 基本信息 | 包名、版本名、版本号、签名、MD5、SHA256、文件大小 |
| 权限分析 | 申请权限列表、危险权限识别、权限组合风险 |
| 组件分析 | Activity、Service、Receiver、Provider 导出检测 |
| 代码特征 | Native 库、加壳检测、混淆检测、敏感 API |

**技术栈**：androguard

---

#### M05 - Android Runner

**职责**：Android 模拟器生命周期管理

**核心功能**：
- 远程 ADB 连接管理
- APK 安装与卸载
- 权限授予
- 应用启动
- 截图捕获
- 触摸/滑动/输入操作
- 活动（Activity）监控

**模拟器配置**：

| 参数 | 值 |
|------|-----|
| 端口范围 | 5555-5558 |
| 设备型号 | Nexus 5 |
| Android 版本 | 11.0 |
| 屏幕分辨率 | 1080x1920 |

---

#### M06 - Traffic Monitor

**职责**：网络流量捕获与分析

**核心功能**：
- mitmproxy 代理配置
- SSL 证书安装
- 流量实时解析
- 白名单过滤
- 敏感域名/IP 识别

**流量处理流程**：

```
APP 网络请求 ──→ mitmproxy ──→ 流量解析 ──→ 白名单过滤
                                              │
                                      ┌───────┴───────┐
                                      ↓               ↓
                                  匹配(忽略)      未匹配(风险分析)
```

---

#### M07 - AI Driver

**职责**：AutoGLM-Phone 集成与操作指令生成

**核心功能**：
- 连接 AI 模型服务
- 截图分析与决策
- 操作指令生成
- 操作执行与验证

**支持的 AI 操作**：

| 操作 | 描述 | 参数 |
|------|------|------|
| `Tap` | 点击坐标 | x, y |
| `Swipe` | 滑动屏幕 | direction: up/down/left/right |
| `Type` | 输入文本 | text |
| `Back` | 返回上一页 | - |
| `Home` | 返回桌面 | - |
| `Wait` | 等待 | duration |

**技术栈**：AutoGLM-Phone-9B + OpenAI 兼容 API

---

#### M08 - Screenshot Manager

**职责**：截图捕获、去重与存储

**核心功能**：
- 远程截图捕获
- 感知哈希去重（防止重复截图）
- MinIO 存储
- Base64 编码（用于报告）

**截图阶段分类**：
- install：安装完成
- launch：应用启动
- nav_tab_*：导航探索
- auto_step_*：自主探索
- search_attempt：搜索场景
- scroll_*：滚动场景

---

#### M09 - App Explorer

**职责**：4 阶段混合应用探索策略

**探索阶段**：

| 阶段 | 名称 | 描述 |
|------|------|------|
| Phase 1 | 基础设置 | 安装 APK、授予权限、启动应用 |
| Phase 2 | 导航探索 | 点击底部导航栏、切换 Tab |
| Phase 3 | 自主探索 | AI 驱动智能探索（最多 50 步） |
| Phase 4 | 场景测试 | 搜索场景、滚动场景 |

**智能跳过机制**：
- 检测登录/支付页面并自动跳过
- 连续错误超过 5 次自动停止

---

#### M10 - Domain Analyzer

**职责**：主控域名识别与分析

**多因子评分模型**：

| 因子 | 分值 | 说明 |
|------|------|------|
| POST/PUT 请求 | +20 | 数据提交行为 |
| 敏感数据传输 | +30 | 包含用户 ID、设备信息等 |
| 非标准端口 | +10 | 非 80/443 端口 |
| 私有 IP 地址 | +50 | 使用内网服务器 |
| 非 HTTPS | +15 | 未加密传输 |
| 请求频率 | +log(count)*2 | 高频请求 |

**白名单过滤**：
- CDN 域名（cloudflare、akamai 等）
- 广告域名（doubleclick、admob 等）
- 统计域名（umeng、google-analytics 等）

---

#### M11 - Report Generator

**职责**：PDF 分析报告生成

**报告结构**：

1. **报告概览**
   - 任务 ID、分析时间
   - APK 文件信息摘要

2. **应用基本信息**
   - 包名、版本、签名
   - MD5、SHA256、文件大小

3. **权限分析**
   - 申请权限列表
   - 危险权限标记
   - 权限风险等级

4. **组件分析**
   - Activity/Service/Receiver/Provider 列表
   - 导出状态检测

5. **网络行为分析**
   - 主控域名识别
   - 请求域名/IP 列表
   - 白名单过滤结果
   - 可疑 C2 标记

6. **运行截图**
   - 按阶段展示截图
   - 操作描述

7. **风险总结**
   - 综合风险等级
   - 风险点汇总
   - 处置建议

**技术栈**：WeasyPrint + Jinja2

---

## 四、分析报告字段定义

### 4.1 静态特征字段

#### 4.1.1 基本信息

| 字段名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| `package_name` | string | 应用包名 | com.example.app |
| `app_name` | string | 应用名称 | 示例应用 |
| `version_name` | string | 版本名 | 1.0.0 |
| `version_code` | integer | 版本号 | 1 |
| `min_sdk` | integer | 最低 SDK | 21 |
| `target_sdk` | integer | 目标 SDK | 33 |
| `file_size` | long | 文件大小（字节） | 52428800 |
| `md5` | string | MD5 哈希 | abc123... |
| `sha256` | string | SHA256 哈希 | def456... |
| `signature` | string | 签名信息 | CN=Example |
| `is_debuggable` | boolean | 是否可调试 | false |
| `is_packed` | boolean | 是否加壳 | false |

#### 4.1.2 权限信息

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `permission_name` | string | 权限名称 |
| `protection_level` | string | 保护级别（normal/dangerous/signature） |
| `description` | string | 权限描述 |
| `risk_level` | string | 风险等级（low/medium/high） |

#### 4.1.3 组件信息

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `component_type` | string | 组件类型（activity/service/receiver/provider） |
| `component_name` | string | 组件完整类名 |
| `is_exported` | boolean | 是否导出 |
| `risk_level` | string | 风险等级 |

---

### 4.2 动态特征字段

#### 4.2.1 网络请求

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `url` | string | 完整 URL |
| `host` | string | 域名 |
| `ip` | string | 解析 IP |
| `port` | integer | 端口 |
| `method` | string | HTTP 方法 |
| `scheme` | string | 协议（http/https） |
| `response_code` | integer | 响应状态码 |
| `content_type` | string | 内容类型 |
| `is_whitelisted` | boolean | 是否在白名单 |

#### 4.2.2 主控域名分析

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `domain` | string | 域名 |
| `score` | float | 业务重要性评分 |
| `confidence` | string | 置信度（high/medium/low） |
| `evidence` | array | 证据列表 |
| `sample_requests` | array | 示例请求 |

#### 4.2.3 运行截图

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `stage` | string | 截图阶段 |
| `description` | string | 操作描述 |
| `timestamp` | datetime | 截图时间 |
| `storage_path` | string | MinIO 存储路径 |

---

### 4.3 网络白名单分类

| 类别 | 描述 | 示例 |
|------|------|------|
| `system` | 系统底噪 | google.com, gstatic.com |
| `cdn` | 知名 CDN | cloudflare.com, akamai.net |
| `analytics` | 统计服务 | umeng.com, talkingdata.net |
| `ads` | 广告服务 | doubleclick.net, admob.com |
| `third_party` | 第三方 SDK | qq.com, weibo.com |
| `custom` | 自定义规则 | 用户自定义域名 |

---

## 五、技术栈与中间件

### 5.1 技术栈总览

| 层级 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| **编程语言** | Python | 3.11+ | 与 AutoGLM 技术栈一致 |
| **API 框架** | FastAPI | 0.100+ | 高性能异步框架 |
| **任务调度** | Celery | 5.3+ | 分布式任务队列 |
| **消息队列** | Redis | 7.0+ | Celery Broker |
| **关系数据库** | MySQL | 8.0+ | 元数据存储 |
| **ORM** | SQLAlchemy | 2.0+ | 数据库操作 |
| **对象存储** | MinIO | 最新版 | APK/截图/报告存储 |
| **流量代理** | mitmproxy | 10.0+ | 流量捕获 |
| **AI 驱动** | AutoGLM-Phone | 9B | 手机 Agent 模型 |
| **PDF 生成** | WeasyPrint | 60+ | HTML 转 PDF |
| **图像处理** | Pillow + imagehash | - | 截图去重 |

### 5.2 服务配置

#### MySQL 配置

```yaml
mysql:
  host: 10.16.129.20
  port: 3306
  database: apk_analysis
  pool_size: 20
  max_overflow: 10
```

#### Redis 配置

```yaml
redis:
  cluster_nodes:
    - 10.16.129.20:7000
    - 10.16.129.20:7001
    - 10.16.129.20:7002
  max_connections: 100
```

#### MinIO 配置

```yaml
minio:
  endpoint: 10.16.129.20:9000
  bucket: apk-analysis
```

#### AI 服务配置

```yaml
ai_service:
  base_url: http://10.16.148.66:6000/v1
  model: autoglm-phone-9b
  max_tokens: 3000
  temperature: 0.1
```

#### Android 模拟器集群

```yaml
emulator_pool:
  - host: 10.16.148.66
    ports: [5555, 5556, 5557, 5558]
```

---

## 六、非功能性需求

### 6.1 性能要求

| 指标 | 目标值 |
|------|--------|
| API 响应时间 | < 500ms (P99) |
| 任务队列吞吐量 | 20-50 并发任务 |
| 单个 APK 分析时间 | < 15 分钟 |
| PDF 报告生成时间 | < 30 秒 |

### 6.2 可用性要求

| 指标 | 目标值 |
|------|--------|
| 系统可用性 | 99.5% |
| 任务成功率 | 95%+ |
| 故障恢复时间 | < 10 分钟 |

### 6.3 安全要求

- API 访问需 Token 认证
- 敏感配置（密码、密钥）使用环境变量
- APK 文件隔离存储
- 分析容器网络隔离

---

## 七、项目目录结构

```
apk-analysis-platform/
├── api/                        # API Gateway
│   ├── main.py                 # FastAPI 入口
│   ├── routers/                # 路由模块
│   │   ├── tasks.py            # 任务管理
│   │   ├── whitelist.py        # 白名单管理
│   │   └── apk.py              # APK 上传
│   └── schemas/                # Pydantic 模型
├── core/                       # 核心模块
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   └── storage.py              # MinIO 封装
├── workers/                    # Celery Workers
│   ├── celery_app.py           # Celery 配置
│   ├── static_analyzer.py      # 静态分析任务
│   ├── dynamic_analyzer.py     # 动态分析任务
│   └── report_generator.py     # 报告生成任务
├── modules/                    # 功能模块
│   ├── apk_analyzer/           # APK 静态分析
│   ├── android_runner/         # Android 容器管理
│   ├── traffic_monitor/        # 流量监控
│   ├── ai_driver/              # AI 驱动层
│   ├── screenshot_manager/     # 截图管理
│   ├── exploration_strategy/   # 应用探索策略
│   ├── domain_analyzer/        # 主控域名分析
│   └── report_generator/       # 报告生成
├── models/                     # 数据模型
│   ├── task.py                 # 任务模型
│   ├── whitelist.py            # 白名单模型
│   └── analysis_result.py      # 分析结果模型
├── templates/                  # 报告模板
│   └── report_enhanced.html    # 增强版报告模板
├── tests/                      # 测试用例
├── docs/                       # 文档
├── requirements.txt
└── README.md
```

---

## 八、参考资料

- [AutoGLM-Phone GitHub](https://github.com/zai-org/AutoGLM)
- [mitmproxy 文档](https://docs.mitmproxy.org/)
- [androguard 文档](https://androguard.readthedocs.io/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Celery 文档](https://docs.celeryq.dev/)

---

## 九、版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-02-18 | AI Agent | 初始版本 |
| v2.0 | 2026-02-20 | AI Agent | 融合增强功能：截图管理、应用探索、主控域名分析 |
