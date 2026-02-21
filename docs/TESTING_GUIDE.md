# 测试用例执行指南

**文档版本**: v1.0
**创建日期**: 2026-02-21
**适用范围**: APK 智能动态分析平台项目任务测试

---

## 📋 文档说明

本文档提供所有任务测试用例的执行指南，包括环境准备、执行方法、结果验证等内容。

---

## 🎯 测试用例总览

### 完成情况统计

| 模块 | 任务数 | 测试类 | 测试方法 | 状态 |
|------|--------|--------|---------|------|
| 模块一：基础设施层 | 3 | 3 | 20 | ✅ 已完成 |
| 模块二：核心分析引擎 | 4 | 4 | 26 | ✅ 已完成 |
| 模块三：智能分析模块 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块四：报告与可视化 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块五：API 层增强 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块六：模拟器管理 | 2 | 2 | 10 | ⏸️ 待创建 |
| 模块七：安全与合规 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块八：测试与质量保证 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块九：DevOps 与部署 | 3 | 3 | 15 | ⏸️ 待创建 |
| 模块十：文档与知识库 | 2 | 2 | 10 | ⏸️ 待创建 |
| **总计** | **29** | **29** | **156** | **29.5%** |

---

## 🔧 环境准备

### 1. 安装测试依赖

```bash
# 激活虚拟环境
source venv/bin/activate

# 安装测试依赖
pip install pytest pytest-cov pytest-asyncio pytest-xdist pytest-html pytest-mock

# 验证安装
pytest --version
```

### 2. 准备测试数据

```bash
# 创建测试数据目录
mkdir -p tests/fixtures
mkdir -p tests/test_data

# 准备测试 APK 文件（可使用小型测试 APK）
# 建议使用小于 5MB 的测试 APK
```

### 3. 配置测试环境

创建 `tests/conftest.py`：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def client():
    """创建测试客户端"""
    from api.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
```

---

## 🚀 测试执行方法

### 一、运行所有测试

```bash
# 运行所有测试用例
pytest tests/task_tests/ -v

# 运行并显示覆盖率
pytest tests/task_tests/ -v --cov=. --cov-report=html

# 并行运行（加速）
pytest tests/task_tests/ -v -n auto
```

### 二、运行指定模块测试

```bash
# 模块一：基础设施层
pytest tests/task_tests/test_module_01_infrastructure.py -v

# 模块二：核心分析引擎
pytest tests/task_tests/test_module_02_core_analysis.py -v
```

### 三、运行指定测试类

```bash
# 数据库连接池监控测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring -v

# 静态分析集成测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration -v

# 场景测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting -v

# AI 决策增强测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced -v

# 流量协议解析测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing -v
```

### 四、运行指定测试方法

```bash
# 测试连接池状态接口
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_pool_status_endpoint -v

# 测试静态分析性能
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration::test_static_analysis_performance -v
```

### 五、生成测试报告

```bash
# 生成 HTML 报告
pytest tests/task_tests/ --html=reports/test_report.html --self-contained-html

# 生成 JUnit XML 报告
pytest tests/task_tests/ --junit-xml=reports/junit.xml

# 生成覆盖率报告
pytest tests/task_tests/ --cov=. --cov-report=html --cov-report=term
```

---

## 📊 详细测试用例执行指南

### 模块一：基础设施层 (test_module_01_infrastructure.py)

#### 任务 1.1: 数据库连接池优化与监控

**测试类**: `TestDatabasePoolMonitoring`

```bash
# 运行所有数据库连接池测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring -v

# 单独测试各项功能
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_pool_status_endpoint -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_connection_leak_detection -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_slow_query_logging -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_prometheus_metrics -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring::test_health_check_endpoint -v
```

**验证标准**:
- ✅ 连接池监控接口返回正确数据
- ✅ 连接泄漏能被检测并告警
- ✅ 慢查询（>1s）被记录
- ✅ Prometheus 指标格式正确
- ✅ 健康检查端点正常工作

#### 任务 1.2: MinIO 存储优化与冗余备份

**测试类**: `TestStorageEnhancements`

```bash
# 运行所有存储增强测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements -v

# 单独测试各项功能
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements::test_storage_capacity_monitoring -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements::test_multipart_upload -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements::test_file_versioning -v
```

**验证标准**:
- ✅ 存储容量统计准确
- ✅ 过期文件自动清理
- ✅ 大文件分片上传成功
- ✅ 文件版本管理正常

#### 任务 1.3: Redis 缓存策略优化

**测试类**: `TestRedisCacheStrategy`

```bash
# 运行所有缓存策略测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy -v

# 单独测试各项功能
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy::test_task_result_caching -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy::test_cache_invalidation -v
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy::test_cache_monitoring -v
```

**验证标准**:
- ✅ 任务结果缓存命中率 > 80%
- ✅ 缓存失效机制正常
- ✅ 缓存监控指标正确

---

### 模块二：核心分析引擎 (test_module_02_core_analysis.py)

#### 任务 2.1: 静态分析功能集成

**测试类**: `TestStaticAnalyzerIntegration`

```bash
# 运行所有静态分析测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration -v

# 单独测试关键功能
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration::test_static_analysis_in_pipeline -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration::test_static_analysis_performance -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration::test_risk_scoring -v
```

**验证标准**:
- ✅ 静态分析在流水线中正确执行
- ✅ 静态分析耗时 < 30秒
- ✅ 风险评分算法准确
- ✅ APK 解析结果可缓存

**前置条件**:
- 准备测试 APK 文件：`tests/fixtures/test.apk`
- APK 文件大小建议 < 5MB

#### 任务 2.2: 动态分析增强 - 场景扩展

**测试类**: `TestScenarioTesting`

```bash
# 运行所有场景测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting -v

# 单独测试场景检测
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting::test_login_scenario_detection -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting::test_payment_scenario_execution -v
```

**验证标准**:
- ✅ 登录场景自动识别
- ✅ 支付场景正确执行
- ✅ 场景报告完整

**注意事项**:
- 需要 Mock Android 模拟器和 AI 驱动器
- 测试数据需包含 UI 元素信息

#### 任务 2.3: AI 驱动优化 - 决策智能增强

**测试类**: `TestAIDecisionEnhanced`

```bash
# 运行所有 AI 决策测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced -v

# 单独测试关键功能
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced::test_exploration_depth_limit -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced::test_loop_detection -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced::test_smart_backtrack -v
```

**验证标准**:
- ✅ 探索深度不超过 50 步
- ✅ 循环界面能被检测
- ✅ 死胡同时能智能回退

#### 任务 2.4: 流量监控增强 - 协议解析

**测试类**: `TestTrafficProtocolParsing`

```bash
# 运行所有流量协议测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing -v

# 单独测试协议解析
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing::test_websocket_capture -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing::test_grpc_parsing -v
pytest tests/task_tests/test_module_02_core_analysis.py::test_https_decryption_performance -v
```

**验证标准**:
- ✅ WebSocket 消息被捕获
- ✅ gRPC 请求被解析
- ✅ HTTPS 解密延迟 < 100ms

---

## 🎯 测试验收标准

### 功能验收

- ✅ 所有测试用例通过率 > 95%
- ✅ 核心功能测试覆盖率 > 85%
- ✅ 无阻塞性 Bug

### 性能验收

- ✅ API 响应时间 < 200ms (P95)
- ✅ 静态分析耗时 < 30s
- ✅ 动态分析耗时 < 10min

### 质量验收

- ✅ 单元测试覆盖率 > 85%
- ✅ 集成测试覆盖率 > 70%
- ✅ 无高危安全漏洞

---

## 🔍 测试结果分析

### 查看测试报告

```bash
# 查看 HTML 测试报告
open reports/test_report.html

# 查看覆盖率报告
open htmlcov/index.html
```

### 分析测试失败

```bash
# 查看失败测试的详细信息
pytest tests/task_tests/ -v --tb=long

# 只运行失败的测试
pytest tests/task_tests/ --lf -v

# 停止于第一个失败
pytest tests/task_tests/ -x -v
```

### 性能分析

```bash
# 测试执行时间分析
pytest tests/task_tests/ --durations=10

# 内存使用分析
pytest tests/task_tests/ --memray
```

---

## 🚨 常见问题与解决方案

### 问题 1: 测试数据库连接失败

**现象**: `ConnectionError: Could not connect to database`

**解决方案**:
```python
# 使用内存数据库进行测试
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
```

### 问题 2: Mock 对象不生效

**现象**: Mock 对象未按预期工作

**解决方案**:
```python
# 确保 Mock 在正确的位置
with patch('modules.apk_analyzer.analyzer.APK') as mock_apk:
    # 配置 Mock 行为
    mock_apk.return_value.get_package.return_value = "com.example"
    # 执行测试
    result = analyzer.analyze("test.apk")
```

### 问题 3: 异步测试失败

**现象**: `RuntimeError: Event loop is closed`

**解决方案**:
```python
# 使用 pytest-asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

### 问题 4: 测试超时

**现象**: 测试长时间运行不结束

**解决方案**:
```bash
# 设置测试超时时间
pytest tests/task_tests/ --timeout=60
```

---

## 📝 测试最佳实践

### 1. 测试隔离

每个测试应该独立运行，不依赖其他测试的状态：

```python
# ❌ 错误：依赖全局状态
global_var = None

def test_1():
    global global_var
    global_var = "value"

def test_2():
    assert global_var == "value"  # 可能失败

# ✅ 正确：使用 fixtures
@pytest.fixture
def test_data():
    return "value"

def test_isolated(test_data):
    assert test_data == "value"
```

### 2. 清晰的断言

```python
# ❌ 错误：断言不清晰
assert response

# ✅ 正确：明确的断言
assert response.status_code == 200
assert "task_id" in response.json()
assert response.json()["status"] == "completed"
```

### 3. 使用参数化

```python
@pytest.mark.parametrize("input,expected", [
    ("valid_input", True),
    ("invalid_input", False),
    ("edge_case", True)
])
def test_validation(input, expected):
    assert validate(input) == expected
```

### 4. Mock 外部依赖

```python
# Mock 外部 API 调用
with patch('requests.get') as mock_get:
    mock_get.return_value.json.return_value = {"data": "test"}
    result = fetch_data()
    assert result == {"data": "test"}
```

---

## 📅 测试执行计划

### 第一阶段：基础设施测试（第 1 周）

```bash
# 第 1 天：数据库连接池测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring -v

# 第 2 天：存储测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements -v

# 第 3 天：缓存测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy -v
```

### 第二阶段：核心分析测试（第 2-3 周）

```bash
# 第 1 周：静态分析测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration -v

# 第 2 周：动态分析和场景测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting -v
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced -v

# 第 3 周：流量监控测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing -v
```

### 第三阶段：后续模块测试（第 4-6 周）

```bash
# 待创建后续模块测试文件后执行
# 模块三至模块十的测试
```

---

## 📞 支持

如有测试问题，请联系：

- **测试负责人**: [待指定]
- **技术支持**: [待指定]

---

**文档位置**: `/docs/TESTING_GUIDE.md`
**测试文件**: `/tests/task_tests/`
**最后更新**: 2026-02-21
