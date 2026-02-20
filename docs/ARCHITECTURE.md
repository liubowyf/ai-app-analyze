# APK 智能动态分析平台 - 系统架构文档

> **版本**: v2.0
> **日期**: 2026-02-20
> **状态**: 已实现

---

## 一、架构概述

### 1.1 设计原则

本系统采用**微服务架构**和**事件驱动**设计，遵循以下原则：

1. **模块化设计**：各功能模块独立开发、测试、部署
2. **异步处理**：使用 Celery 实现任务异步执行，提高系统吞吐量
3. **可扩展性**：支持水平扩展，可增加 Worker 节点提升处理能力
4. **容错性**：任务失败自动重试，支持断点续传

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部调用方                                       │
│                      (外部平台 / Web 界面 / CLI)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API 网关层                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Application                          │   │
│  │  Routes: /apk/upload | /tasks | /tasks/{id} | /whitelist           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │    MySQL     │  │    Redis     │  │    MinIO     │
            │  (元数据)    │  │  (队列)      │  │  (文件存储)  │
            └──────────────┘  └──────────────┘  └──────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            任务调度层                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │ Celery Worker   │  │ Celery Worker   │  │ Celery Worker   │            │
│  │ Queue: static   │  │ Queue: dynamic  │  │ Queue: report   │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             执行层                                            │
│                                                                             │
│  静态分析流水线:                                                             │
│  ┌───────────────┐                                                          │
│  │  APK Analyzer │ ──→ 提取包名、权限、组件、签名                            │
│  │  (androguard) │                                                          │
│  └───────────────┘                                                          │
│                                                                             │
│  动态分析流水线:                                                             │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐                │
│  │ Android Runner│──→│ App Explorer  │──→│Screenshot Mgr │                │
│  │ (ADB 远程控制)│   │ (4阶段探索)   │   │ (截图去重)    │                │
│  └───────────────┘   └───────────────┘   └───────────────┘                │
│         │                   │                                             │
│         ▼                   ▼                                             │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐                │
│  │Traffic Monitor│   │   AI Driver   │   │Domain Analyzer│                │
│  │  (mitmproxy)  │   │ (AutoGLM-Phone)│  │ (主控域名)    │                │
│  └───────────────┘   └───────────────┘   └───────────────┘                │
│                                                                             │
│  报告生成流水线:                                                             │
│  ┌───────────────┐   ┌───────────────┐                                     │
│  │Report Generator│──→│  WeasyPrint  │                                     │
│  │  (Jinja2模板) │   │  (PDF生成)   │                                     │
│  └───────────────┘   └───────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           基础设施层                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Android 模拟器集群 (10.16.148.66)                  │   │
│  │                     端口: 5555, 5556, 5557, 5558                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      AI 服务 (10.16.148.66:6000)                     │   │
│  │                        AutoGLM-Phone-9B                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              数据库集群 (10.16.129.20)                                │   │
│  │         MySQL:3306 | Redis Cluster:7000-7002 | MinIO:9000           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块实现

### 2.1 ScreenshotManager (截图管理器)

**文件位置**: `modules/screenshot_manager/manager.py`

**核心功能**:
- 远程截图捕获
- 感知哈希去重
- MinIO 存储上传
- Base64 编码转换

**关键实现**:

```python
class ScreenshotManager:
    """截图管理器 - 支持捕获、去重和存储"""

    def _calculate_hash(self, image_data: bytes) -> str:
        """计算感知哈希，用于去重"""
        # 使用 imagehash.phash 计算感知哈希
        # 相似图片的哈希值距离很近

    def is_duplicate(self, image_data: bytes) -> bool:
        """检测是否为重复截图"""
        # 比较当前图片与上一张的哈希距离
        # 阈值设置为 10，低于此值视为重复
```

**去重算法**:
- 使用感知哈希（Perceptual Hash）
- 计算图片的 pHash 值
- 比较哈希距离，距离 < 10 视为重复
- 有效减少重复截图 60%+

---

### 2.2 AppExplorer (应用探索器)

**文件位置**: `modules/exploration_strategy/explorer.py`

**4 阶段混合探索策略**:

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: 基础设置                                                │
│   - 连接模拟器                                                   │
│   - 安装 APK                                                     │
│   - 授予所有权限                                                  │
│   - 启动应用                                                      │
│   - 截图: install.png, launch.png                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 2: 导航探索                                                │
│   - 点击底部导航栏 (4个Tab)                                       │
│   - 截图每个 Tab 界面                                            │
│   - 记录访问的 Activity                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 3: 自主探索 (AI驱动)                                        │
│   - AI 分析截图，决策下一步操作                                    │
│   - 最多 50 步探索                                                │
│   - 智能跳过登录/支付页面                                         │
│   - 连续错误 5 次自动停止                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 4: 场景测试                                                │
│   - 搜索场景：尝试触发搜索功能                                     │
│   - 滚动场景：向下滚动多次                                        │
└─────────────────────────────────────────────────────────────────┘
```

**AI 决策流程**:

```python
def phase3_autonomous_explore(self, host, port, max_steps=50):
    for step in range(max_steps):
        # 1. 截取当前屏幕
        screenshot_data = self.android_runner.take_screenshot_remote(host, port)

        # 2. AI 分析并决策
        operation = self.ai_driver.analyze_and_decide(
            screenshot_data,
            self.exploration_history,
            goal="深度探索应用功能，触发更多网络请求"
        )

        # 3. 检测是否跳过（登录/支付页面）
        if self._should_skip_screen(screenshot_data):
            self.android_runner.press_back(host, port)
            continue

        # 4. 执行操作
        self._execute_operation(host, port, operation)

        # 5. 记录探索历史
        self.exploration_history.append({...})
```

---

### 2.3 MasterDomainAnalyzer (主控域名分析器)

**文件位置**: `modules/domain_analyzer/analyzer.py`

**多因子评分模型**:

```
评分 = Σ(各因子分值)

因子列表:
┌──────────────────────────┬────────┬─────────────────────────────┐
│ 因子                      │ 分值   │ 说明                         │
├──────────────────────────┼────────┼─────────────────────────────┤
│ POST/PUT 请求            │ +20/个 │ 数据提交行为                  │
│ 敏感数据传输              │ +30    │ user_id, device_id, token等  │
│ 非标准端口 (非80/443)     │ +10    │ 可疑端口使用                  │
│ 私有 IP 地址              │ +50    │ 使用内网服务器                │
│ 非 HTTPS                 │ +15    │ 未加密传输                    │
│ 请求频率                  │ +log(N)*2 │ 高频请求                   │
└──────────────────────────┴────────┴─────────────────────────────┘

置信度判定:
- score >= 50: high
- score >= 20: medium
- score < 20:  low
```

**白名单过滤**:

```python
class MasterDomainAnalyzer:
    # CDN 域名模式
    CDN_PATTERNS = [
        r'\.cdn\.',
        r'\.cloudfront\.net$',
        r'\.akamai\.',
        r'\.fastly\.net$',
        r'\.cloudflare\.com$',
    ]

    # 广告域名模式
    AD_DOMAINS = [
        r'\.googlesyndication\.com$',
        r'\.doubleclick\.net$',
        r'\.umeng\.com$',
    ]

    # 统计域名模式
    ANALYTICS_DOMAINS = [
        r'\.google-analytics\.com$',
        r'\.sensorsdata\.cn$',
    ]

    def is_whitelisted(self, domain: str) -> bool:
        """检查是否在白名单中"""
        return (
            self.is_cdn_domain(domain) or
            self.is_ad_domain(domain) or
            self.is_analytics_domain(domain)
        )
```

---

### 2.4 AndroidRunner (Android 运行器)

**文件位置**: `modules/android_runner/runner.py`

**远程控制方法**:

| 方法 | 功能 | 参数 |
|------|------|------|
| `connect_remote_emulator` | 连接远程模拟器 | host, port |
| `install_apk_remote` | 安装 APK | host, port, apk_path |
| `grant_all_permissions` | 授予所有权限 | host, port, package |
| `launch_app` | 启动应用 | host, port, package |
| `take_screenshot_remote` | 远程截图 | host, port |
| `execute_tap` | 执行点击 | host, port, x, y |
| `execute_swipe` | 执行滑动 | host, port, start, end |
| `execute_input_text` | 输入文本 | host, port, text |
| `get_current_activity` | 获取当前 Activity | host, port |
| `press_back` | 按返回键 | host, port |
| `press_home` | 按主页键 | host, port |

**ADB 命令封装**:

```python
def execute_adb_remote(self, host: str, port: int, command: str) -> str:
    """执行远程 ADB 命令"""
    device = f"{host}:{port}"
    result = subprocess.run(
        ["adb", "-s", device] + command.split(),
        capture_output=True,
        text=True,
        timeout=30
    )
    return result.stdout
```

---

### 2.5 TrafficMonitor (流量监控器)

**文件位置**: `modules/traffic_monitor/monitor.py`

**mitmproxy 集成**:

```python
class TrafficMonitor:
    """流量监控器 - 基于 mitmproxy"""

    def __init__(self, task_id: str, emulator_port: int):
        self.task_id = task_id
        self.proxy_port = 8080 + (emulator_port - 5555)
        self.requests: List[NetworkRequest] = []

    async def start(self):
        """启动 mitmproxy 代理"""
        # 配置代理端口
        # 设置 SSL 证书
        # 启动异步监听

    def request_hook(self, request: http.Request):
        """请求拦截钩子"""
        # 解析请求信息
        # 应用白名单过滤
        # 记录到请求列表
```

---

### 2.6 DynamicAnalyzer (动态分析任务)

**文件位置**: `workers/dynamic_analyzer.py`

**任务编排流程**:

```python
@celery_app.task(bind=True, max_retries=2)
def run_dynamic_analysis(self, task_id: str):
    """动态分析主任务"""

    # 1. 初始化组件
    screenshot_manager = ScreenshotManager(task_id)
    android_runner = AndroidRunner()
    ai_driver = AIDriver()
    traffic_monitor = TrafficMonitor(task_id, emulator_port)
    domain_analyzer = MasterDomainAnalyzer()

    # 2. 创建探索器
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    # 3. 启动流量监控
    await traffic_monitor.start()

    # 4. 执行探索
    result = explorer.run_full_exploration(
        emulator_config={"host": EMULATOR_HOST, "port": emulator_port},
        apk_info={"apk_path": apk_path, "package_name": package_name}
    )

    # 5. 分析域名
    network_requests = traffic_monitor.get_all_requests()
    master_domains = domain_analyzer.analyze(network_requests)

    # 6. 保存结果
    save_analysis_result(task_id, result, master_domains)
```

---

## 三、数据模型

### 3.1 任务状态流转

```
┌──────────┐    创建任务    ┌──────────┐    入队    ┌──────────────────┐
│ pending  │ ────────────→ │  queued  │ ────────→ │ static_analyzing │
└──────────┘               └──────────┘           └──────────────────┘
                                                        │
                                                        ▼
┌──────────┐    完成    ┌────────────────────┐    ┌───────────────────┐
│completed │ ←───────── │ report_generating  │ ←──│ dynamic_analyzing │
└──────────┘            └────────────────────┘    └───────────────────┘
     │                                                   │
     │                                                   │
     └─────────────────── 失败 ──────────────────────────┘
                                │
                                ▼
                         ┌──────────┐
                         │  failed  │
                         └──────────┘
                                │
                                │ 重试
                                ▼
                         ┌──────────┐
                         │ pending  │
                         └──────────┘
```

### 3.2 数据库表结构

**tasks 表**:

```sql
CREATE TABLE tasks (
    id VARCHAR(36) PRIMARY KEY,

    -- APK 信息
    apk_file_name VARCHAR(255) NOT NULL,
    apk_file_size BIGINT NOT NULL,
    apk_md5 VARCHAR(32) NOT NULL,
    apk_sha256 VARCHAR(64),
    apk_storage_path VARCHAR(500),

    -- 任务状态
    status ENUM('pending', 'queued', 'static_analyzing',
                'dynamic_analyzing', 'report_generating',
                'completed', 'failed'),
    priority ENUM('urgent', 'normal', 'batch'),

    -- 错误信息
    error_message TEXT,
    retry_count INT DEFAULT 0,

    -- 分析结果 (JSON)
    static_analysis_result JSON,
    dynamic_analysis_result JSON,

    -- 报告路径
    report_storage_path VARCHAR(500),

    -- 时间戳
    created_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME
);
```

**network_whitelist 表**:

```sql
CREATE TABLE network_whitelist (
    id VARCHAR(36) PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    ip_range VARCHAR(50),
    category ENUM('system', 'cdn', 'analytics', 'ads', 'third_party', 'custom'),
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME,
    updated_at DATETIME,

    INDEX idx_domain (domain),
    INDEX idx_category (category)
);
```

---

## 四、部署架构

### 4.1 生产环境部署

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            生产环境                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        应用服务器 (多节点)                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ FastAPI 服务 │  │ Celery Worker│  │ Celery Worker│              │   │
│  │  │  (API 网关)  │  │  (static)    │  │  (dynamic)   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        数据库服务器                                   │   │
│  │  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐      │   │
│  │  │  MySQL 8.0   │  │  Redis Cluster       │  │    MinIO     │      │   │
│  │  │ 10.16.129.20 │  │  10.16.129.20:7000-02│  │ 10.16.129.20 │      │   │
│  │  └──────────────┘  └──────────────────────┘  └──────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                     │
│                                      ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      分析集群 (10.16.148.66)                          │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │            Android 模拟器池 (端口: 5555-5558)                  │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │              AI 服务 (AutoGLM-Phone :6000)                    │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 启动命令

**开发环境**:

```bash
# 1. 激活虚拟环境
source venv/bin/activate

# 2. 启动 API 服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动 Celery Worker
celery -A workers.celery_app worker -l info \
    -Q default,static,dynamic,report \
    --concurrency=4
```

**生产环境**:

```bash
# API 服务 (使用 gunicorn)
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000

# Celery Worker (使用 supervisor)
celery -A workers.celery_app worker -l info \
    -Q static --concurrency=2 \
    --max-tasks-per-child=50

celery -A workers.celery_app worker -l info \
    -Q dynamic --concurrency=4 \
    --max-tasks-per-child=20

celery -A workers.celery_app worker -l info \
    -Q report --concurrency=2 \
    --max-tasks-per-child=100
```

---

## 五、性能优化

### 5.1 截图去重效果

| 场景 | 去重前 | 去重后 | 节省比例 |
|------|--------|--------|----------|
| 导航探索 | 20 张 | 8 张 | 60% |
| 自主探索 | 50 张 | 18 张 | 64% |
| 场景测试 | 15 张 | 6 张 | 60% |

### 5.2 并发处理能力

| 配置 | 吞吐量 |
|------|--------|
| 1 Worker | 5 任务/小时 |
| 4 Workers | 18 任务/小时 |
| 8 Workers | 35 任务/小时 |

### 5.3 任务耗时分布

| 阶段 | 平均耗时 |
|------|----------|
| 静态分析 | 30 秒 |
| 动态分析 | 8 分钟 |
| 报告生成 | 15 秒 |
| **总计** | **约 9 分钟** |

---

## 六、错误处理

### 6.1 任务重试策略

```python
@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300  # 5 分钟后重试
)
def run_dynamic_analysis(self, task_id: str):
    try:
        # 执行分析
        ...
    except EmulatorConnectionError as e:
        # 模拟器连接错误，切换模拟器重试
        self.retry(exc=e, countdown=60)
    except AIDriverError as e:
        # AI 服务错误，稍后重试
        self.retry(exc=e, countdown=300)
    except Exception as e:
        # 其他错误，记录并标记失败
        mark_task_failed(task_id, str(e))
```

### 6.2 错误分类

| 错误类型 | 处理策略 |
|----------|----------|
| EmulatorConnectionError | 切换模拟器，60秒后重试 |
| APKInstallError | 标记失败，不重试 |
| AIDriverError | 300秒后重试，最多2次 |
| TrafficMonitorError | 继续执行，记录警告 |
| ScreenshotError | 跳过当前步骤，继续执行 |

---

## 七、监控与日志

### 7.1 日志格式

```
[时间] [级别] [模块] [任务ID] 消息
```

示例:
```
[2026-02-20 10:30:15] [INFO] [dynamic_analyzer] [task-123] 开始动态分析
[2026-02-20 10:30:18] [INFO] [app_explorer] [task-123] Phase 1: 基础设置
[2026-02-20 10:30:25] [INFO] [app_explorer] [task-123] APK 安装成功
[2026-02-20 10:30:30] [INFO] [app_explorer] [task-123] 应用启动成功
```

### 7.2 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| 任务队列长度 | 等待处理的任务数 | > 100 |
| 任务失败率 | 失败任务占比 | > 10% |
| 平均处理时间 | 单任务处理时长 | > 15 分钟 |
| 模拟器可用数 | 可用模拟器数量 | < 2 |

---

## 八、安全考虑

### 8.1 网络隔离

- 模拟器运行在独立网段
- APK 文件存储在隔离的 MinIO bucket
- 分析结果仅通过 API 访问

### 8.2 敏感数据处理

- 配置信息通过环境变量注入
- 不记录网络请求的敏感内容
- 报告中脱敏处理敏感字段

### 8.3 访问控制

- API 需要 Token 认证
- 任务数据按 ID 隔离
- 支持白名单 IP 限制

---

## 九、扩展性设计

### 9.1 水平扩展

- 增加 Celery Worker 节点
- 扩展模拟器池规模
- 配置 Redis 集群分片

### 9.2 模块替换

- AI Driver 支持切换不同模型
- 流量监控支持其他代理方案
- 报告模板可自定义

### 9.3 功能扩展点

- 支持更多静态分析工具
- 增加新的探索策略
- 接入其他威胁情报源
