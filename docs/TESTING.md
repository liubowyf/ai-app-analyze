# 测试指南

本文档介绍 APK 智能动态分析平台的测试框架、测试结构、运行方法和最佳实践。

---

## 目录

- [测试概览](#测试概览)
- [测试环境](#测试环境)
- [测试结构](#测试结构)
- [运行测试](#运行测试)
- [测试分类](#测试分类)
- [编写测试](#编写测试)
- [测试覆盖率](#测试覆盖率)

---

## 测试概览

项目采用 **pytest** 作为测试框架,配合 **unittest.mock** 进行依赖模拟。测试覆盖了 API 路由、数据模型、存储服务、核心模块等关键组件。

### 测试统计

| 类别 | 文件数 | 代码行数 | 测试用例数 |
|------|--------|---------|-----------|
| API 测试 | 3 | 657 | ~30 |
| 模型测试 | 3 | 985 | ~40 |
| 存储测试 | 1 | 274 | ~15 |
| 配置测试 | 2 | 68 | ~5 |
| 模块测试 | 5 | 180 | ~10 |
| **总计** | **17** | **2257** | **~100** |

---

## 测试环境

### 依赖安装

```bash
# 安装测试依赖
pip install pytest pytest-cov pytest-asyncio

# 或通过 requirements.txt 安装
pip install -r requirements.txt
```

### 测试配置

项目根目录可创建 `pytest.ini` 配置文件:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --cov=. --cov-report=html --cov-report=term
```

---

## 测试结构

```
tests/
├── conftest.py                      # Pytest 配置和共享 fixtures
│
├── API 路由测试
│   ├── test_apk_router.py           # APK 上传接口测试
│   ├── test_tasks_router.py         # 任务管理接口测试
│   └── test_whitelist_router.py     # 白名单接口测试
│
├── 数据模型测试
│   ├── test_task_model.py           # 任务模型测试
│   ├── test_analysis_result_model.py # 分析结果模型测试
│   └── test_whitelist_model.py      # 白名单模型测试
│
├── 核心服务测试
│   ├── test_storage.py              # MinIO 存储服务测试
│   ├── test_database.py             # 数据库连接测试
│   └── test_config.py               # 配置管理测试
│
├── 功能模块测试
│   ├── test_api_main.py             # FastAPI 主程序测试
│   ├── test_android_runner_enhanced.py # Android 模拟器控制测试
│   ├── test_app_explorer.py         # 应用探索策略测试
│   ├── test_screenshot_manager.py   # 截图管理器测试
│   ├── test_domain_analyzer.py      # 域名分析器测试
│   ├── test_static_analyzer.py      # 静态分析器测试
│   └── test_celery_app.py           # Celery 配置测试
```

---

## 运行测试

### 运行所有测试

```bash
# 运行所有测试
pytest

# 详细输出
pytest -v

# 显示测试覆盖率
pytest --cov=. --cov-report=html

# 并行运行 (需要 pytest-xdist)
pytest -n auto
```

### 运行指定测试文件

```bash
# 运行单个测试文件
pytest tests/test_apk_router.py

# 运行多个测试文件
pytest tests/test_apk_router.py tests/test_tasks_router.py
```

### 运行指定测试用例

```bash
# 运行指定测试类
pytest tests/test_apk_router.py::TestAPKUpload

# 运行指定测试方法
pytest tests/test_apk_router.py::TestAPKUpload::test_upload_apk_success
```

### 运行带标记的测试

```bash
# 运行慢速测试
pytest -m slow

# 跳过慢速测试
pytest -m "not slow"

# 运行需要模拟器的测试
pytest -m emulator
```

### 测试输出选项

```bash
# 详细输出 + 失败时的回溯信息
pytest -v --tb=long

# 只显示失败的测试
pytest --tb=short -x

# 生成 HTML 报告
pytest --html=report.html --self-contained-html

# 生成 JUnit XML 报告 (用于 CI)
pytest --junit-xml=junit.xml
```

---

## 测试分类

### 1. API 路由测试

#### test_apk_router.py
测试 APK 文件上传接口。

**测试范围**:
- APK 文件上传成功
- 文件大小验证
- MD5 哈希计算
- 文件存储到 MinIO
- 数据库记录创建

**关键测试用例**:
```python
class TestAPKUpload:
    test_upload_apk_success()        # 测试成功上传
    test_upload_apk_invalid_file()   # 测试无效文件
    test_upload_apk_file_too_large() # 测试文件过大
```

#### test_tasks_router.py
测试任务管理接口。

**测试范围**:
- 任务创建
- 任务状态查询
- 任务列表获取
- 任务取消
- 错误处理

**关键测试用例**:
```python
class TestTasksRouter:
    test_create_task()           # 创建任务
    test_get_task_status()       # 查询状态
    test_list_tasks()            # 任务列表
    test_cancel_task()           # 取消任务
```

#### test_whitelist_router.py
测试白名单管理接口。

**测试范围**:
- 白名单规则创建
- 规则查询
- 规则更新
- 规则删除
- 规则验证

**关键测试用例**:
```python
class TestWhitelistRouter:
    test_create_whitelist_rule()  # 创建规则
    test_get_whitelist_rules()    # 查询规则
    test_update_whitelist_rule()  # 更新规则
    test_delete_whitelist_rule()  # 删除规则
```

---

### 2. 数据模型测试

#### test_task_model.py
测试任务数据模型。

**测试范围**:
- 任务创建和属性
- 状态转换
- 优先级设置
- 时间戳自动更新
- 序列化和反序列化

**关键测试用例**:
```python
test_create_task()              # 创建任务实例
test_task_status_transitions()  # 状态转换逻辑
test_task_priority_levels()     # 优先级枚举
test_task_timestamps()          # 时间戳自动管理
```

#### test_analysis_result_model.py
测试分析结果数据模型。

**测试范围**:
- 分析结果创建
- 静态分析数据
- 动态分析数据
- 网络请求数据
- JSON 序列化

**关键测试用例**:
```python
test_create_analysis_result()           # 创建分析结果
test_static_analysis_data()             # 静态分析数据
test_dynamic_analysis_data()            # 动态分析数据
test_network_requests_serialization()   # 网络请求序列化
```

#### test_whitelist_model.py
测试白名单数据模型。

**测试范围**:
- 白名单规则创建
- 规则类型验证
- 正则表达式验证
- 规则匹配逻辑

**关键测试用例**:
```python
test_create_whitelist_rule()    # 创建白名单规则
test_rule_type_validation()     # 规则类型验证
test_regex_pattern_validation() # 正则表达式验证
test_rule_matching()            # 规则匹配逻辑
```

---

### 3. 存储服务测试

#### test_storage.py
测试 MinIO 存储服务。

**测试范围**:
- 文件上传
- 文件下载
- 文件删除
- URL 生成
- 存储桶管理

**关键测试用例**:
```python
class TestStorageClient:
    test_upload_file()        # 上传文件
    test_download_file()      # 下载文件
    test_delete_file()        # 删除文件
    test_generate_url()       # 生成访问 URL
    test_bucket_operations()  # 存储桶操作
```

---

### 4. 核心配置测试

#### test_database.py
测试数据库连接和会话管理。

**测试范围**:
- 数据库连接创建
- 会话管理
- 连接池配置
- SSL 连接

#### test_config.py
测试配置管理。

**测试范围**:
- 环境变量加载
- 配置项验证
- 默认值设置

---

### 5. 功能模块测试

#### test_android_runner_enhanced.py
测试 Android 模拟器控制模块。

**测试范围**:
- 模拟器连接
- ADB 命令执行
- APK 安装
- 截图捕获
- 用户交互模拟

**注意事项**:
- 需要模拟 Docker 环境
- 需要模拟 ADB 连接
- 部分测试需要真实模拟器

#### test_app_explorer.py
测试应用探索策略模块。

**测试范围**:
- 探索器初始化
- 4 阶段探索策略
- 探索结果记录

#### test_screenshot_manager.py
测试截图管理模块。

**测试范围**:
- 截图捕获
- 图片去重
- 图片存储

#### test_domain_analyzer.py
测试域名分析器模块。

**测试范围**:
- 域名提取
- 主控域名识别
- 多因子评分

#### test_static_analyzer.py
测试静态分析器模块。

**测试范围**:
- APK 解析
- 权限提取
- 组件分析

#### test_celery_app.py
测试 Celery 配置。

**测试范围**:
- Celery 应用配置
- 任务路由配置
- 队列设置

---

## 编写测试

### 测试命名规范

```python
# 文件命名: test_<module_name>.py
test_apk_router.py
test_task_model.py

# 类命名: Test<Feature>
class TestAPKUpload:
    pass

# 方法命名: test_<action>_<expected_result>
def test_upload_apk_success():
    pass

def test_upload_apk_invalid_file():
    pass
```

### 使用 Fixtures

```python
# conftest.py 中定义共享 fixtures
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """创建测试客户端"""
    from api.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    from unittest.mock import MagicMock
    return MagicMock()

# 测试中使用 fixtures
def test_upload_apk(client, mock_db):
    response = client.post("/api/v1/apk/upload", ...)
    assert response.status_code == 200
```

### 使用 Mock

```python
from unittest.mock import patch, MagicMock

def test_storage_upload():
    """测试存储上传"""
    with patch("core.storage.Minio") as mock_minio:
        # 配置 mock 行为
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        mock_client.put_object.return_value = None

        # 测试上传逻辑
        from core.storage import storage_client
        result = storage_client.upload_file("test.apk", b"content")

        # 验证调用
        assert result is True
        mock_client.put_object.assert_called_once()
```

### 测试异步代码

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    result = await some_async_function()
    assert result is not None
```

### 测试异常

```python
import pytest

def test_invalid_input():
    """测试异常处理"""
    with pytest.raises(ValueError) as exc_info:
        raise ValueError("Invalid input")

    assert str(exc_info.value) == "Invalid input"
```

---

## 测试覆盖率

### 生成覆盖率报告

```bash
# 生成终端报告
pytest --cov=. --cov-report=term

# 生成 HTML 报告
pytest --cov=. --cov-report=html

# 查看 HTML 报告
open htmlcov/index.html
```

### 覆盖率目标

| 模块 | 目标覆盖率 | 当前覆盖率 |
|------|-----------|-----------|
| API 路由 | ≥ 80% | ~75% |
| 数据模型 | ≥ 70% | ~70% |
| 存储服务 | ≥ 85% | ~85% |
| 核心模块 | ≥ 60% | ~50% |

### 提高覆盖率

1. **补充边界测试**: 测试边界条件和异常情况
2. **增加集成测试**: 测试模块间的交互
3. **完善 Mock**: 确保所有依赖都被正确模拟
4. **覆盖错误分支**: 测试错误处理逻辑

---

## 测试最佳实践

### 1. 测试隔离

每个测试应该独立运行,不依赖其他测试的状态。

```python
# ❌ 错误: 依赖全局状态
global_var = None

def test_1():
    global global_var
    global_var = "value"

def test_2():
    assert global_var == "value"  # 可能失败

# ✅ 正确: 使用 fixtures
@pytest.fixture
def test_data():
    return "value"

def test_isolated(test_data):
    assert test_data == "value"
```

### 2. 清晰的断言

```python
# ❌ 错误: 断言不清晰
assert response

# ✅ 正确: 明确的断言
assert response.status_code == 200
assert "task_id" in response.json()
```

### 3. 测试文档

```python
def test_upload_apk_success():
    """
    测试成功上传 APK 文件。

    验证:
    1. 返回状态码 200
    2. 返回任务 ID
    3. 文件成功存储到 MinIO
    4. 数据库中创建了任务记录
    """
    # 测试代码
    pass
```

### 4. 使用参数化

```python
import pytest

@pytest.mark.parametrize("status,expected", [
    ("pending", True),
    ("running", True),
    ("completed", True),
    ("invalid", False),
])
def test_valid_status(status, expected):
    """测试不同状态值"""
    from models.task import TaskStatus
    is_valid = status in [s.value for s in TaskStatus]
    assert is_valid == expected
```

---

## CI/CD 集成

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: test
          MYSQL_DATABASE: apk_analysis
        ports:
          - 3306:3306

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 常见问题

### 1. 测试数据库连接失败

**问题**: 测试时无法连接到数据库

**解决方案**:
```python
# 使用内存数据库或 mock
@pytest.fixture
def mock_db():
    from unittest.mock import MagicMock
    return MagicMock()
```

### 2. 模拟 Docker 连接

**问题**: 测试 Android 模拟器控制时需要 Docker

**解决方案**:
```python
# 使用 mock 模拟 Docker
with patch('docker.from_env') as mock_docker:
    mock_client = MagicMock()
    mock_docker.return_value = mock_client
    # 测试代码
```

### 3. 异步测试失败

**问题**: 异步函数测试报错

**解决方案**:
```python
# 安装 pytest-asyncio
pip install pytest-asyncio

# 使用 asyncio 标记
@pytest.mark.asyncio
async def test_async():
    result = await async_function()
    assert result is not None
```

### 4. 测试覆盖率低

**问题**: 某些模块覆盖率不足

**解决方案**:
1. 查看覆盖率报告,找到未覆盖的代码
2. 补充边界条件测试
3. 增加异常处理测试
4. 使用参数化测试覆盖多种情况

---

## 测试命令速查

```bash
# 运行所有测试
pytest

# 运行指定文件
pytest tests/test_apk_router.py

# 详细输出
pytest -v

# 显示代码覆盖率
pytest --cov=. --cov-report=html

# 并行运行
pytest -n auto

# 只运行失败的测试
pytest --lf

# 停止于第一个失败
pytest -x

# 生成 HTML 报告
pytest --html=report.html --self-contained-html

# 运行慢速测试
pytest -m slow

# 跳过慢速测试
pytest -m "not slow"
```

---

**最后更新**: 2026-02-20
**测试文件数**: 17
**测试用例数**: ~100
**代码行数**: 2257
