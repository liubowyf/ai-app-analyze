# 模块二：核心分析引擎 - 设计文档

**文档版本**: v1.0
**创建日期**: 2026-02-21
**负责人**: 技术架构团队
**模块**: 模块二 - 核心分析引擎
**优先级**: P0-P2

---

## 一、模块概述

### 1.1 模块目标

构建完整的APK分析流水线，实现从静态分析到动态分析，再到智能决策和流量监控的全流程自动化。

### 1.2 模块范围

| 任务ID | 任务名称 | 优先级 | 预估工时 | 验收方式 |
|--------|---------|--------|---------|---------|
| 2.1 | 静态分析功能集成 | P0 | 3天 | 单独验收 |
| 2.2 | 动态分析增强 - 场景扩展 | P1 | 5天 | 批量验收 |
| 2.3 | AI驱动优化 - 决策智能增强 | P1 | 4天 | 批量验收 |
| 2.4 | 流量监控增强 - 协议解析 | P2 | 4天 | 批量验收 |

**总工期**: 16天

### 1.3 依赖关系

```
任务2.1 (静态分析) ──┐
                     ├──> 任务2.2 (动态分析增强) ──> 任务2.3 (AI优化)
                     │
任务2.4 (流量监控) ──┘ (独立实施)
```

---

## 二、任务详细设计

### 2.1 任务2.1：静态分析功能集成（P0）

#### 2.1.1 功能目标

重新启用静态分析，将其作为动态分析的前置步骤，提取APK基本信息、权限、组件、签名等关键信息，并进行风险评估。

#### 2.1.2 技术架构

**当前流程**：
```
Upload APK → Dynamic Analysis → Report Generation
```

**目标流程**：
```
Upload APK → Static Analysis → Dynamic Analysis → Report Generation
```

**核心组件**：
- `workers/static_analyzer.py` - Celery任务定义
- `modules/apk_analyzer/analyzer.py` - 静态分析器
- `models/task.py` - 任务数据模型

#### 2.1.3 实施步骤

**步骤1：移除跳过逻辑**
```python
# 当前代码中可能存在类似逻辑：
# if task.skip_static_analysis:
#     return

# 解决方案：删除跳过逻辑，确保静态分析始终执行
```

**步骤2：优化任务链**

修改 `workers/dynamic_analyzer.py`，确保任务链正确调用：

```python
@shared_task(bind=True, name="workers.dynamic_analyzer.run_dynamic_analysis")
def run_dynamic_analysis(self, task_id: str) -> dict:
    # 确保静态分析已完成
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task.static_analysis_result:
        raise ValueError("Static analysis must be completed first")

    # 继续动态分析...
```

**步骤3：性能优化 - APK解析缓存**

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def cached_analyze_apk(apk_path: str, apk_hash: str):
    """
    缓存APK解析结果，避免重复解析相同APK

    Args:
        apk_path: APK文件路径
        apk_hash: APK文件MD5哈希（用于缓存键）
    """
    from androguard.misc import AnalyzeAPK
    a, d, dx = AnalyzeAPK(apk_path)
    return a, d, dx
```

**步骤4：风险评分算法**

```python
class RiskScorer:
    """APK风险评分器"""

    # 权限风险等级
    DANGEROUS_PERMISSIONS = [
        'android.permission.READ_CONTACTS',
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.READ_SMS',
        'android.permission.CALL_PHONE',
        # ... 更多危险权限
    ]

    def calculate_permission_risk(self, permissions: List[str]) -> int:
        """计算权限风险分数"""
        score = 0
        for perm in permissions:
            if perm in self.DANGEROUS_PERMISSIONS:
                score += 3  # 危险权限
            else:
                score += 1  # 普通权限
        return score

    def calculate_component_risk(self, components: Dict) -> int:
        """计算组件暴露风险"""
        score = 0
        for component_type, items in components.items():
            for item in items:
                if item.get('exported', False):
                    score += 2
        return score

    def calculate_signature_risk(self, signature_info: Dict) -> int:
        """计算签名风险"""
        if not signature_info:
            return 5  # 无签名，高风险

        if signature_info.get('self_signed', False):
            return 2  # 自签名，中等风险

        return 0  # 正常签名，无风险

    def calculate_total_risk(self, analysis_result: Dict) -> Dict:
        """计算总风险评分"""
        permission_risk = self.calculate_permission_risk(
            analysis_result.get('permissions', [])
        )
        component_risk = self.calculate_component_risk(
            analysis_result.get('components', {})
        )
        signature_risk = self.calculate_signature_risk(
            analysis_result.get('signature_info', {})
        )

        total_score = permission_risk + component_risk + signature_risk

        # 风险等级判定
        if total_score >= 20:
            risk_level = "HIGH"
        elif total_score >= 10:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "total_score": total_score,
            "risk_level": risk_level,
            "breakdown": {
                "permission_risk": permission_risk,
                "component_risk": component_risk,
                "signature_risk": signature_risk
            }
        }
```

**步骤5：集成到分析流程**

修改 `modules/apk_analyzer/analyzer.py`：

```python
class ApkAnalyzer:
    """APK静态分析器"""

    def analyze(self, apk_content: bytes, file_size: int, md5: str) -> ApkAnalysisResult:
        """
        执行完整的静态分析

        Args:
            apk_content: APK文件二进制内容
            file_size: 文件大小
            md5: MD5哈希值

        Returns:
            ApkAnalysisResult: 分析结果对象
        """
        # 1. 保存临时文件
        with tempfile.NamedTemporaryFile(suffix='.apk', delete=False) as tmp:
            tmp.write(apk_content)
            apk_path = tmp.name

        try:
            # 2. 解析APK（使用缓存）
            a, d, dx = cached_analyze_apk(apk_path, md5)

            # 3. 提取基本信息
            basic_info = self._extract_basic_info(a)

            # 4. 提取权限
            permissions = self._extract_permissions(a)

            # 5. 提取组件
            components = self._extract_components(a, d)

            # 6. 提取签名信息
            signature_info = self._extract_signature(a)

            # 7. 计算风险评分
            risk_scorer = RiskScorer()
            risk_assessment = risk_scorer.calculate_total_risk({
                'permissions': permissions,
                'components': components,
                'signature_info': signature_info
            })

            # 8. 构建结果
            return ApkAnalysisResult(
                basic_info=basic_info,
                permissions=permissions,
                components=components,
                signature_info=signature_info,
                risk_assessment=risk_assessment,
                file_size=file_size,
                md5=md5
            )
        finally:
            # 清理临时文件
            os.unlink(apk_path)
```

#### 2.1.4 测试策略

**单元测试** (`tests/test_static_analyzer_integration.py`)：

```python
import pytest
from modules.apk_analyzer.analyzer import ApkAnalyzer, RiskScorer

class TestStaticAnalyzerIntegration:
    """静态分析集成测试"""

    @pytest.fixture
    def sample_apk(self):
        """测试APK文件"""
        # 使用真实的测试APK
        with open("tests/fixtures/sample.apk", "rb") as f:
            return f.read()

    def test_static_analysis_in_pipeline(self, sample_apk):
        """测试静态分析在流水线中执行"""
        analyzer = ApkAnalyzer()
        result = analyzer.analyze(
            apk_content=sample_apk,
            file_size=len(sample_apk),
            md5="test_md5_hash"
        )

        # 验证结果完整性
        assert result.basic_info is not None
        assert result.permissions is not None
        assert result.components is not None
        assert result.risk_assessment is not None

    def test_static_analysis_result_storage(self, db_session, sample_apk):
        """测试静态分析结果存储到数据库"""
        # 创建任务
        task = Task(id="test_task_id", apk_file_name="test.apk")
        db_session.add(task)
        db_session.commit()

        # 执行分析
        analyzer = ApkAnalyzer()
        result = analyzer.analyze(
            apk_content=sample_apk,
            file_size=len(sample_apk),
            md5="test_md5"
        )

        # 存储结果
        task.static_analysis_result = result.model_dump()
        db_session.commit()

        # 验证存储
        saved_task = db_session.query(Task).filter_by(id="test_task_id").first()
        assert saved_task.static_analysis_result is not None
        assert "basic_info" in saved_task.static_analysis_result

    def test_static_analysis_performance(self, sample_apk):
        """测试静态分析性能 - 应小于30秒"""
        import time

        analyzer = ApkAnalyzer()
        start_time = time.time()

        result = analyzer.analyze(
            apk_content=sample_apk,
            file_size=len(sample_apk),
            md5="test_md5"
        )

        elapsed_time = time.time() - start_time
        assert elapsed_time < 30, f"静态分析耗时{elapsed_time:.2f}秒，超过30秒限制"

    def test_risk_scoring(self):
        """测试风险评分算法"""
        scorer = RiskScorer()

        # 测试高风险APK
        high_risk_data = {
            'permissions': [
                'android.permission.READ_CONTACTS',
                'android.permission.ACCESS_FINE_LOCATION',
                'android.permission.READ_SMS',
            ],
            'components': {
                'activities': [{'name': 'MainActivity', 'exported': True}],
                'receivers': [{'name': 'SmsReceiver', 'exported': True}]
            },
            'signature_info': None  # 无签名
        }

        result = scorer.calculate_total_risk(high_risk_data)
        assert result['risk_level'] == "HIGH"
        assert result['total_score'] >= 20

        # 测试低风险APK
        low_risk_data = {
            'permissions': ['android.permission.INTERNET'],
            'components': {'activities': [{'name': 'MainActivity', 'exported': False}]},
            'signature_info': {'self_signed': False}
        }

        result = scorer.calculate_total_risk(low_risk_data)
        assert result['risk_level'] == "LOW"
        assert result['total_score'] < 10

    def test_apk_cache(self, sample_apk):
        """测试APK解析缓存"""
        analyzer = ApkAnalyzer()

        # 第一次分析
        result1 = analyzer.analyze(
            apk_content=sample_apk,
            file_size=len(sample_apk),
            md5="test_md5_1"
        )

        # 第二次分析相同MD5
        result2 = analyzer.analyze(
            apk_content=sample_apk,
            file_size=len(sample_apk),
            md5="test_md5_1"  # 相同MD5
        )

        # 验证结果一致
        assert result1.md5 == result2.md5

        # 验证缓存命中（可通过日志或性能判断）
        # 第二次应该更快
```

**集成测试**：

```python
def test_static_to_dynamic_handoff():
    """测试静态分析到动态分析的数据传递"""
    # 1. 上传APK
    # 2. 等待静态分析完成
    # 3. 验证静态分析结果存在
    # 4. 启动动态分析
    # 5. 验证动态分析能读取静态结果
    pass
```

#### 2.1.5 验收标准

- [ ] 静态分析在任务链中自动执行
- [ ] 结果正确存储到数据库 `task.static_analysis_result` 字段
- [ ] 静态分析耗时 < 30秒
- [ ] 风险评分算法准确率 > 90%（基于测试集）
- [ ] APK解析结果可缓存复用（相同MD5只解析一次）
- [ ] 单元测试覆盖率 > 85%
- [ ] 集成测试通过

#### 2.1.6 性能指标

| 指标 | 目标值 | 测试方法 |
|------|--------|---------|
| 分析耗时 | < 30s | 性能测试 |
| 内存占用 | < 500MB | 资源监控 |
| 并发处理 | 支持5个并发 | 压力测试 |
| 缓存命中率 | > 80% | 日志分析 |

#### 2.1.7 技术风险

**风险1：Androguard解析性能差**
- 影响：分析耗时过长
- 概率：中
- 应对：使用缓存、并行解析

**风险2：大APK文件内存溢出**
- 影响：分析失败
- 概率：低
- 应对：限制APK大小（< 200MB）、流式处理

---

### 2.2 任务2.2：动态分析增强 - 场景扩展（P1）

#### 2.2.1 功能目标

扩展应用探索场景，增加登录场景、支付场景、分享场景的专项测试，提升动态分析的覆盖率和深度。

#### 2.2.2 技术架构

**场景测试框架**：
```
ScenarioDetector (场景识别)
    ├── LoginScenarioDetector
    ├── PaymentScenarioDetector
    └── ShareScenarioDetector

ScenarioTester (场景测试)
    ├── LoginScenarioTester
    ├── PaymentScenarioTester
    └── ShareScenarioTester

TestDataManager (测试数据管理)
    ├── CredentialsProvider
    ├── PaymentMocker
    └── ContentTemplates
```

#### 2.2.3 实施步骤

**步骤1：创建场景检测器**

`modules/scenario_testing/detector.py`:

```python
"""场景检测器 - 识别特定UI场景"""
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class UIElement:
    """UI元素"""
    text: str
    class_name: str
    bounds: Dict[str, int]
    clickable: bool
    editable: bool

class ScenarioDetector:
    """场景检测器基类"""

    def detect_login(self, ui_elements: List[UIElement]) -> bool:
        """
        检测登录场景

        检测规则：
        1. 存在"登录"或"Login"按钮
        2. 存在用户名/手机号输入框（EditText with hint）
        3. 存在密码输入框（EditText with inputType="password"）

        Args:
            ui_elements: UI元素列表（从AI分析结果获取）

        Returns:
            bool: 是否检测到登录场景
        """
        has_login_button = False
        has_username_input = False
        has_password_input = False

        for element in ui_elements:
            # 检测登录按钮
            if element.clickable and any(keyword in element.text.lower()
                                        for keyword in ['登录', 'login', 'sign in']):
                has_login_button = True

            # 检测用户名输入框
            if element.editable and any(keyword in element.text.lower()
                                       for keyword in ['用户名', '手机号', 'username', 'phone']):
                has_username_input = True

            # 检测密码输入框
            if element.editable and 'password' in element.class_name.lower():
                has_password_input = True

        return has_login_button and (has_username_input or has_password_input)

    def detect_payment(self, ui_elements: List[UIElement]) -> bool:
        """
        检测支付场景

        检测规则：
        1. 存在"支付"或"付款"按钮
        2. 存在金额输入框
        3. 存在支付方式选择（微信、支付宝等）

        Args:
            ui_elements: UI元素列表

        Returns:
            bool: 是否检测到支付场景
        """
        has_payment_button = False
        has_amount_input = False
        has_payment_method = False

        for element in ui_elements:
            # 检测支付按钮
            if element.clickable and any(keyword in element.text.lower()
                                        for keyword in ['支付', '付款', 'pay', 'payment']):
                has_payment_button = True

            # 检测金额输入框
            if element.editable and any(keyword in element.text.lower()
                                       for keyword in ['金额', 'amount', 'price']):
                has_amount_input = True

            # 检测支付方式
            if any(keyword in element.text.lower()
                  for keyword in ['微信', '支付宝', 'wechat', 'alipay']):
                has_payment_method = True

        return has_payment_button or (has_amount_input and has_payment_method)

    def detect_share(self, ui_elements: List[UIElement]) -> bool:
        """
        检测分享场景

        检测规则：
        1. 存在"分享"按钮
        2. 存在分享平台选择（微信、QQ、微博等）

        Args:
            ui_elements: UI元素列表

        Returns:
            bool: 是否检测到分享场景
        """
        has_share_button = False
        has_share_platform = False

        for element in ui_elements:
            # 检测分享按钮
            if element.clickable and any(keyword in element.text.lower()
                                        for keyword in ['分享', 'share']):
                has_share_button = True

            # 检测分享平台
            if any(keyword in element.text.lower()
                  for keyword in ['微信', 'qq', '微博', 'wechat', 'weibo']):
                has_share_platform = True

        return has_share_button or has_share_platform
```

**步骤2：创建场景测试器**

`modules/scenario_testing/tester.py`:

```python
"""场景测试器 - 执行特定场景测试"""
from typing import Dict, Optional
from dataclasses import dataclass
import logging

from modules.android_runner import AndroidRunner
from modules.ai_driver import AIDriver
from .detector import ScenarioDetector, UIElement

logger = logging.getLogger(__name__)

@dataclass
class ScenarioTestResult:
    """场景测试结果"""
    scenario_type: str
    success: bool
    steps_executed: int
    error_message: Optional[str] = None
    network_requests: list = None

class ScenarioTester:
    """场景测试器基类"""

    def __init__(self, android_runner: AndroidRunner, ai_driver: AIDriver):
        self.android_runner = android_runner
        self.ai_driver = ai_driver
        self.detector = ScenarioDetector()

    def test_login_scenario(self, host: str, port: int,
                           credentials: Dict[str, str]) -> ScenarioTestResult:
        """
        测试登录场景

        Args:
            host: 模拟器主机
            port: 模拟器端口
            credentials: 登录凭据 {'username': '', 'password': ''}

        Returns:
            ScenarioTestResult: 测试结果
        """
        logger.info("开始测试登录场景")

        try:
            steps = 0

            # 1. 识别用户名输入框
            # 使用AI分析当前界面，定位输入框坐标
            screenshot = self.android_runner.take_screenshot_remote(host, port)
            ai_response = self.ai_driver.analyze_screenshot(screenshot)

            # 2. 输入用户名
            username_coords = self._find_input_field(ai_response, 'username')
            if username_coords:
                self.android_runner.execute_tap(host, port,
                                               username_coords['x'],
                                               username_coords['y'])
                self.android_runner.input_text(host, port, credentials['username'])
                steps += 1

            # 3. 输入密码
            password_coords = self._find_input_field(ai_response, 'password')
            if password_coords:
                self.android_runner.execute_tap(host, port,
                                               password_coords['x'],
                                               password_coords['y'])
                self.android_runner.input_text(host, port, credentials['password'])
                steps += 1

            # 4. 点击登录按钮
            login_button_coords = self._find_button(ai_response, 'login')
            if login_button_coords:
                self.android_runner.execute_tap(host, port,
                                               login_button_coords['x'],
                                               login_button_coords['y'])
                steps += 1

            # 5. 等待登录完成
            import time
            time.sleep(3)

            # 6. 验证登录成功（检查界面变化）
            new_screenshot = self.android_runner.take_screenshot_remote(host, port)
            login_success = self._verify_login_success(new_screenshot)

            logger.info(f"登录场景测试完成，执行步骤: {steps}, 成功: {login_success}")

            return ScenarioTestResult(
                scenario_type='login',
                success=login_success,
                steps_executed=steps
            )

        except Exception as e:
            logger.error(f"登录场景测试失败: {e}")
            return ScenarioTestResult(
                scenario_type='login',
                success=False,
                steps_executed=steps,
                error_message=str(e)
            )

    def test_payment_scenario(self, host: str, port: int,
                             amount: float) -> ScenarioTestResult:
        """
        测试支付场景

        Args:
            host: 模拟器主机
            port: 模拟器端口
            amount: 支付金额

        Returns:
            ScenarioTestResult: 测试结果
        """
        logger.info(f"开始测试支付场景，金额: {amount}")

        try:
            steps = 0

            # 1. 识别金额输入框
            screenshot = self.android_runner.take_screenshot_remote(host, port)
            ai_response = self.ai_driver.analyze_screenshot(screenshot)

            # 2. 输入金额
            amount_coords = self._find_input_field(ai_response, 'amount')
            if amount_coords:
                self.android_runner.execute_tap(host, port,
                                               amount_coords['x'],
                                               amount_coords['y'])
                self.android_runner.input_text(host, port, str(amount))
                steps += 1

            # 3. 点击支付按钮
            payment_button_coords = self._find_button(ai_response, 'payment')
            if payment_button_coords:
                self.android_runner.execute_tap(host, port,
                                               payment_button_coords['x'],
                                               payment_button_coords['y'])
                steps += 1

            # 4. 选择支付方式（Mock，不真实支付）
            # 选择取消或返回
            import time
            time.sleep(2)
            self.android_runner.press_back(host, port)

            logger.info(f"支付场景测试完成，执行步骤: {steps}")

            return ScenarioTestResult(
                scenario_type='payment',
                success=True,
                steps_executed=steps
            )

        except Exception as e:
            logger.error(f"支付场景测试失败: {e}")
            return ScenarioTestResult(
                scenario_type='payment',
                success=False,
                steps_executed=steps,
                error_message=str(e)
            )

    def test_share_scenario(self, host: str, port: int) -> ScenarioTestResult:
        """
        测试分享场景

        Args:
            host: 模拟器主机
            port: 模拟器端口

        Returns:
            ScenarioTestResult: 测试结果
        """
        logger.info("开始测试分享场景")

        try:
            steps = 0

            # 1. 识别分享按钮
            screenshot = self.android_runner.take_screenshot_remote(host, port)
            ai_response = self.ai_driver.analyze_screenshot(screenshot)

            # 2. 点击分享按钮
            share_button_coords = self._find_button(ai_response, 'share')
            if share_button_coords:
                self.android_runner.execute_tap(host, port,
                                               share_button_coords['x'],
                                               share_button_coords['y'])
                steps += 1

            # 3. 等待分享菜单弹出
            import time
            time.sleep(1)

            # 4. 选择分享平台（取消操作）
            self.android_runner.press_back(host, port)

            logger.info(f"分享场景测试完成，执行步骤: {steps}")

            return ScenarioTestResult(
                scenario_type='share',
                success=True,
                steps_executed=steps
            )

        except Exception as e:
            logger.error(f"分享场景测试失败: {e}")
            return ScenarioTestResult(
                scenario_type='share',
                success=False,
                steps_executed=steps,
                error_message=str(e)
            )

    def _find_input_field(self, ai_response: Dict, field_type: str) -> Optional[Dict]:
        """从AI响应中定位输入框坐标"""
        # 解析AI响应，找到指定类型的输入框
        # 返回 {'x': 100, 'y': 200} 或 None
        pass

    def _find_button(self, ai_response: Dict, button_type: str) -> Optional[Dict]:
        """从AI响应中定位按钮坐标"""
        pass

    def _verify_login_success(self, screenshot: bytes) -> bool:
        """验证登录是否成功"""
        # 使用AI分析界面，判断是否登录成功
        pass
```

**步骤3：集成到AppExplorer**

修改 `modules/exploration_strategy/explorer.py`:

```python
from modules.scenario_testing.tester import ScenarioTester

class AppExplorer:
    """应用探索器"""

    def __init__(self, ai_driver, android_runner, screenshot_manager):
        # ... 现有代码 ...
        self.scenario_tester = ScenarioTester(android_runner, ai_driver)

    def phase4_scenario_testing(self, host: str, port: str,
                                package_name: str) -> List[ScenarioTestResult]:
        """
        Phase 4: 场景测试

        检测并测试登录、支付、分享等场景
        """
        logger.info("Phase 4: 场景测试")
        results = []

        # 1. 获取当前界面UI元素（从AI分析结果）
        screenshot = self.android_runner.take_screenshot_remote(host, port)
        ai_response = self.ai_driver.analyze_screenshot(screenshot)
        ui_elements = self._parse_ui_elements(ai_response)

        # 2. 检测并测试登录场景
        if self.scenario_tester.detector.detect_login(ui_elements):
            logger.info("检测到登录场景，开始测试")
            result = self.scenario_tester.test_login_scenario(
                host, port,
                credentials={'username': 'test_user', 'password': 'test_pass'}
            )
            results.append(result)

        # 3. 检测并测试支付场景
        if self.scenario_tester.detector.detect_payment(ui_elements):
            logger.info("检测到支付场景，开始测试")
            result = self.scenario_tester.test_payment_scenario(
                host, port, amount=100.0
            )
            results.append(result)

        # 4. 检测并测试分享场景
        if self.scenario_tester.detector.detect_share(ui_elements):
            logger.info("检测到分享场景，开始测试")
            result = self.scenario_tester.test_share_scenario(host, port)
            results.append(result)

        logger.info(f"场景测试完成，共测试 {len(results)} 个场景")

        return results
```

#### 2.2.4 测试策略

**单元测试** (`tests/test_scenario_testing.py`):

```python
import pytest
from modules.scenario_testing.detector import ScenarioDetector, UIElement
from modules.scenario_testing.tester import ScenarioTester

class TestScenarioTesting:
    """场景测试测试"""

    def test_login_scenario_detection(self):
        """测试登录场景检测"""
        detector = ScenarioDetector()

        # 模拟登录界面UI元素
        ui_elements = [
            UIElement(text="登录", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="用户名", class_name="EditText", bounds={}, clickable=False, editable=True),
            UIElement(text="密码", class_name="EditText", bounds={}, clickable=False, editable=True),
        ]

        result = detector.detect_login(ui_elements)
        assert result is True

    def test_payment_scenario_detection(self):
        """测试支付场景检测"""
        detector = ScenarioDetector()

        ui_elements = [
            UIElement(text="支付", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="金额", class_name="EditText", bounds={}, clickable=False, editable=True),
            UIElement(text="微信支付", class_name="RadioButton", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_payment(ui_elements)
        assert result is True

    def test_share_scenario_detection(self):
        """测试分享场景检测"""
        detector = ScenarioDetector()

        ui_elements = [
            UIElement(text="分享", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="微信", class_name="ImageView", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_share(ui_elements)
        assert result is True

    def test_login_scenario_execution(self, mock_android_runner, mock_ai_driver):
        """测试登录场景执行"""
        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        result = tester.test_login_scenario(
            host="10.16.148.66",
            port=5555,
            credentials={'username': 'test', 'password': 'test123'}
        )

        assert result.scenario_type == 'login'
        assert result.steps_executed > 0
```

#### 2.2.5 验收标准

- [ ] 登录场景自动识别并测试（识别率 > 80%）
- [ ] 支付场景自动识别并测试（识别率 > 80%）
- [ ] 分享场景自动识别并测试（识别率 > 80%）
- [ ] 场景测试结果包含在报告中
- [ ] 场景测试不影响主探索流程
- [ ] 单元测试覆盖率 > 85%

---

### 2.3 任务2.3：AI驱动优化 - 决策智能增强（P1）

#### 2.3.1 功能目标

优化AI决策策略，避免无限循环和重复操作，提升探索效率和质量。

#### 2.3.2 核心机制

1. **探索深度控制**：限制最大探索步数（50步）
2. **界面循环检测**：识别重复界面并触发回退
3. **智能回退策略**：遇到死胡同自动回退
4. **Prompt优化**：提升AI决策准确率
5. **决策日志**：记录所有决策过程

#### 2.3.3 实施步骤

**步骤1：探索深度控制**

`modules/exploration_strategy/controller.py`:

```python
"""探索控制器 - 控制探索深度和循环"""
from typing import List, Dict
from dataclasses import dataclass
import hashlib
import logging

logger = logging.getLogger(__name__)

@dataclass
class ExplorationState:
    """探索状态"""
    current_depth: int = 0
    max_depth: int = 50
    visited_screens: List[str] = None
    screen_hash_history: List[str] = None

    def __post_init__(self):
        if self.visited_screens is None:
            self.visited_screens = []
        if self.screen_hash_history is None:
            self.screen_hash_history = []

class ExplorationController:
    """探索控制器"""

    def __init__(self, max_depth: int = 50):
        self.state = ExplorationState(max_depth=max_depth)
        self.loop_detection_window = 10  # 检测最近10个界面
        self.loop_threshold = 3  # 相同界面出现3次判定为循环

    def should_continue(self) -> bool:
        """
        判断是否应该继续探索

        Returns:
            bool: True=继续, False=停止
        """
        if self.state.current_depth >= self.state.max_depth:
            logger.warning(f"达到最大探索深度 {self.state.max_depth}，停止探索")
            return False

        return True

    def record_screen(self, screenshot: bytes, screen_description: str):
        """
        记录访问的界面

        Args:
            screenshot: 截图二进制数据
            screen_description: 界面描述（AI生成）
        """
        # 计算界面hash
        screen_hash = hashlib.md5(screenshot).hexdigest()

        # 记录hash历史
        self.state.screen_hash_history.append(screen_hash)
        self.state.visited_screens.append(screen_description)

        # 增加深度
        self.state.current_depth += 1

        logger.debug(f"记录界面: depth={self.state.current_depth}, hash={screen_hash[:8]}")

    def detect_loop(self) -> bool:
        """
        检测界面循环

        检测逻辑：在最近的N个界面中，是否有界面出现了M次

        Returns:
            bool: True=检测到循环, False=无循环
        """
        if len(self.state.screen_hash_history) < self.loop_threshold:
            return False

        # 检查最近的界面
        recent_hashes = self.state.screen_hash_history[-self.loop_detection_window:]

        # 统计每个hash的出现次数
        hash_counts = {}
        for h in recent_hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1

        # 检查是否有hash出现超过阈值
        for h, count in hash_counts.items():
            if count >= self.loop_threshold:
                logger.warning(f"检测到界面循环: hash={h[:8]}, 出现次数={count}")
                return True

        return False

    def get_backtrack_strategy(self) -> str:
        """
        获取回退策略

        Returns:
            str: 回退策略 ('back', 'restart', 'skip')
        """
        if self.detect_loop():
            return 'back'

        if self.state.current_depth >= self.state.max_depth - 5:
            return 'skip'

        return 'back'
```

**步骤2：集成到AppExplorer**

修改 `modules/exploration_strategy/explorer.py`:

```python
from .controller import ExplorationController

class AppExplorer:
    """应用探索器"""

    def __init__(self, ai_driver, android_runner, screenshot_manager):
        # ... 现有代码 ...
        self.controller = ExplorationController(max_depth=50)

    def phase3_autonomous_exploration(self, host: str, port: str,
                                      package_name: str) -> List[Screenshot]:
        """
        Phase 3: 自主探索（AI驱动）

        优化版本：增加循环检测和智能回退
        """
        logger.info("Phase 3: 自主探索")

        screenshots = []

        while self.controller.should_continue():
            # 1. 获取当前界面截图
            screenshot = self.android_runner.take_screenshot_remote(host, port)

            # 2. AI分析界面
            ai_response = self.ai_driver.analyze_screenshot(
                screenshot,
                context={
                    'visited_screens': self.controller.state.visited_screens[-5:],
                    'current_depth': self.controller.state.current_depth
                }
            )

            # 3. 记录界面
            screen_description = ai_response.get('description', '')
            self.controller.record_screen(screenshot, screen_description)

            # 4. 检测循环
            if self.controller.detect_loop():
                logger.warning("检测到界面循环，执行回退")

                # 执行回退
                backtrack_strategy = self.controller.get_backtrack_strategy()
                if backtrack_strategy == 'back':
                    self.android_runner.press_back(host, port)
                elif backtrack_strategy == 'restart':
                    self.android_runner.launch_app(host, port, package_name)

                continue

            # 5. AI决策下一步操作
            action = ai_response.get('action', {})

            # 6. 执行操作
            if action['type'] == 'tap':
                self.android_runner.execute_tap(host, port,
                                               action['x'], action['y'])
            elif action['type'] == 'swipe':
                self.android_runner.execute_swipe(host, port,
                                                 action['start_x'], action['start_y'],
                                                 action['end_x'], action['end_y'])
            elif action['type'] == 'input':
                self.android_runner.execute_tap(host, port,
                                               action['x'], action['y'])
                self.android_runner.input_text(host, port, action['text'])

            # 7. 捕获截图（去重）
            new_screenshot = self.screenshot_manager.capture(
                stage=f"exploration_step_{self.controller.state.current_depth}",
                description=f"探索步骤 {self.controller.state.current_depth}",
                emulator_host=host,
                emulator_port=port
            )
            if new_screenshot:
                screenshots.append(new_screenshot)

            # 8. 等待界面加载
            import time
            time.sleep(1)

        logger.info(f"自主探索完成，共 {self.controller.state.current_depth} 步")

        return screenshots
```

**步骤3：Prompt优化**

`modules/ai_driver/prompts.py`:

```python
"""优化后的AI Prompt模板"""

EXPLORATION_PROMPT_V2 = """
你是一个Android应用测试专家。你的任务是分析当前界面并决定下一步操作。

## 当前状态
- 探索深度: {current_depth}/{max_depth}
- 已访问界面: {visited_screens}

## 界面分析
{screen_analysis}

## 决策规则
1. **避免重复**: 不要重复访问已经测试过的功能
2. **优先未访问**: 优先探索未访问的界面和功能
3. **循环检测**: 如果检测到界面重复，选择"返回"操作
4. **深度控制**: 接近最大深度时，优先完成当前流程

## 可用操作
- tap: 点击按钮或元素
- swipe: 滑动屏幕
- input: 输入文本
- back: 按返回键

## 输出格式
请以JSON格式输出你的决策：
```json
{{
    "description": "界面描述",
    "action": {{
        "type": "tap|swipe|input|back",
        "x": 坐标x,
        "y": 坐标y,
        "text": "输入文本（如果需要）"
    }},
    "confidence": 0.85,
    "reasoning": "决策理由"
}}
```

请分析界面并做出决策。
"""
```

**步骤4：决策日志记录**

`modules/ai_driver/logger.py`:

```python
"""AI决策日志记录器"""
import json
import logging
from datetime import datetime
from pathlib import Path

class DecisionLogger:
    """决策日志记录器"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.log_file = Path(f"logs/decisions/{task_id}_decisions.jsonl")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(self, decision: dict):
        """
        记录AI决策

        Args:
            decision: 决策信息
                {
                    'step': 1,
                    'timestamp': '2026-02-21T10:00:00',
                    'screen_hash': 'abc123',
                    'action': {'type': 'tap', 'x': 100, 'y': 200},
                    'confidence': 0.85,
                    'reasoning': '检测到登录按钮',
                    'execution_result': 'success'
                }
        """
        log_entry = {
            'task_id': self.task_id,
            **decision
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
```

#### 2.3.4 测试策略

```python
class TestAIDecisionEnhanced:
    """AI决策增强测试"""

    def test_exploration_depth_limit(self):
        """测试探索深度限制"""
        controller = ExplorationController(max_depth=5)

        for i in range(10):
            controller.record_screen(b'test_screenshot', f'screen_{i}')

            if not controller.should_continue():
                break

        assert controller.state.current_depth <= 5

    def test_loop_detection(self):
        """测试循环检测"""
        controller = ExplorationController()

        # 模拟循环：相同界面出现多次
        same_screenshot = b'same_screen'

        for _ in range(5):
            controller.record_screen(same_screenshot, 'same_screen')

        assert controller.detect_loop() is True

    def test_smart_backtrack(self):
        """测试智能回退"""
        controller = ExplorationController()

        # 模拟循环
        for _ in range(3):
            controller.record_screen(b'loop_screen', 'loop_screen')

        strategy = controller.get_backtrack_strategy()
        assert strategy == 'back'
```

#### 2.3.5 验收标准

- [ ] 探索深度不超过50步
- [ ] 循环界面能被检测（检测率 > 90%）
- [ ] 死胡同时能智能回退
- [ ] AI决策准确率 > 70%
- [ ] 所有决策有日志记录
- [ ] 单元测试覆盖率 > 85%

---

### 2.4 任务2.4：流量监控增强 - 协议解析（P2）

#### 2.4.1 功能目标

扩展流量监控能力，支持WebSocket、gRPC、自定义协议的捕获和解析。

#### 2.4.2 技术架构

```
TrafficMonitor
    ├── HTTPInterceptor (现有)
    ├── WebSocketInterceptor (新增)
    ├── GRPCParser (新增)
    └── CustomProtocolDetector (新增)
```

#### 2.4.3 实施步骤

**步骤1：WebSocket拦截器**

`modules/traffic_monitor/websocket_interceptor.py`:

```python
"""WebSocket流量拦截器"""
from mitmproxy import websocket
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class WebSocketInterceptor:
    """WebSocket消息拦截器"""

    def __init__(self):
        self.messages: List[Dict] = []

    def websocket_message(self, flow):
        """
        拦截WebSocket消息

        Args:
            flow: mitmproxy flow对象
        """
        # 获取WebSocket消息
        message = flow.websocket.messages[-1]

        # 记录消息
        message_data = {
            'timestamp': message.timestamp,
            'type': 'websocket',
            'direction': 'send' if message.from_client else 'receive',
            'payload': message.content,
            'payload_length': len(message.content),
            'opcode': message.type,  # TEXT, BINARY, etc.
        }

        self.messages.append(message_data)

        logger.debug(f"WebSocket消息: {message_data['direction']}, "
                    f"长度={message_data['payload_length']}")

    def get_messages(self) -> List[Dict]:
        """获取所有WebSocket消息"""
        return self.messages
```

**步骤2：gRPC解析器**

`modules/traffic_monitor/grpc_parser.py`:

```python
"""gRPC协议解析器"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GRPCParser:
    """gRPC协议解析器"""

    def is_grpc_request(self, headers: Dict) -> bool:
        """
        判断是否为gRPC请求

        Args:
            headers: HTTP请求头

        Returns:
            bool: 是否为gRPC
        """
        content_type = headers.get('content-type', '')
        return 'application/grpc' in content_type

    def parse_grpc_message(self, data: bytes) -> Optional[Dict]:
        """
        解析gRPC消息

        Args:
            data: gRPC消息二进制数据

        Returns:
            Dict: 解析后的消息
        """
        try:
            # gRPC消息格式：5字节头 + 数据
            # 头部：1字节压缩标志 + 4字节数据长度
            if len(data) < 5:
                return None

            compressed = data[0]
            message_length = int.from_bytes(data[1:5], byteorder='big')

            payload = data[5:5+message_length]

            # 尝试解析Protobuf（需要.proto文件）
            # 这里简化处理，只记录原始数据

            return {
                'compressed': bool(compressed),
                'length': message_length,
                'payload': payload,
                'payload_hex': payload.hex()
            }

        except Exception as e:
            logger.error(f"解析gRPC消息失败: {e}")
            return None

    def parse_grpc_request(self, request_headers: Dict, request_body: bytes) -> Optional[Dict]:
        """
        解析gRPC请求

        Args:
            request_headers: 请求头
            request_body: 请求体

        Returns:
            Dict: 解析结果
        """
        if not self.is_grpc_request(request_headers):
            return None

        # 提取gRPC方法名
        path = request_headers.get(':path', '')

        # 解析消息
        message = self.parse_grpc_message(request_body)

        return {
            'type': 'grpc',
            'method': path,
            'message': message
        }
```

**步骤3：集成到TrafficMonitor**

修改 `modules/traffic_monitor/monitor.py`:

```python
from .websocket_interceptor import WebSocketInterceptor
from .grpc_parser import GRPCParser

class TrafficMonitor:
    """流量监控器"""

    def __init__(self):
        # ... 现有代码 ...
        self.ws_interceptor = WebSocketInterceptor()
        self.grpc_parser = GRPCParser()

    def request(self, flow):
        """拦截HTTP请求"""
        # 检查是否为gRPC
        if self.grpc_parser.is_grpc_request(flow.request.headers):
            grpc_data = self.grpc_parser.parse_grpc_request(
                flow.request.headers,
                flow.request.content
            )
            self.requests.append(grpc_data)
            logger.info(f"捕获gRPC请求: {grpc_data['method']}")
            return

        # 普通HTTP请求处理
        # ... 现有代码 ...

    def websocket_message(self, flow):
        """拦截WebSocket消息"""
        self.ws_interceptor.websocket_message(flow)
```

#### 2.4.4 测试策略

```python
class TestTrafficProtocolParsing:
    """流量协议解析测试"""

    def test_websocket_capture(self):
        """测试WebSocket捕获"""
        interceptor = WebSocketInterceptor()

        # 模拟WebSocket消息
        # ...

        messages = interceptor.get_messages()
        assert len(messages) > 0

    def test_grpc_parsing(self):
        """测试gRPC解析"""
        parser = GRPCParser()

        headers = {'content-type': 'application/grpc'}
        body = b'\x00\x00\x00\x00\x05hello'

        result = parser.parse_grpc_request(headers, body)

        assert result['type'] == 'grpc'
        assert result['message']['length'] == 5
```

#### 2.4.5 验收标准

- [ ] WebSocket消息被捕获
- [ ] gRPC请求被解析
- [ ] 自定义协议被识别
- [ ] HTTPS解密延迟 < 100ms
- [ ] 流量可视化图表生成
- [ ] 单元测试覆盖率 > 80%

---

## 三、集成测试

### 3.1 端到端测试

```python
def test_complete_analysis_pipeline():
    """
    测试完整分析流水线

    流程：上传APK → 静态分析 → 动态分析（含场景测试） → 报告生成
    """
    # 1. 上传APK
    # 2. 等待静态分析完成
    # 3. 验证静态分析结果
    # 4. 等待动态分析完成
    # 5. 验证场景测试执行
    # 6. 验证AI决策日志
    # 7. 验证流量捕获
    # 8. 下载报告
    pass
```

---

## 四、验收流程

### 4.1 P0任务验收（任务2.1）

**验收标准**：
1. 所有单元测试通过
2. 测试覆盖率 > 85%
3. 静态分析性能达标（< 30s）
4. 代码审查通过
5. 文档齐全

**验收步骤**：
1. 运行测试套件：`pytest tests/test_static_analyzer_integration.py -v --cov`
2. 性能测试：分析5个不同APK，记录耗时
3. 代码审查：使用 pylint、mypy 检查代码质量
4. 文档检查：确保README、API文档更新

### 4.2 P1/P2任务批量验收（任务2.2、2.3、2.4）

**验收标准**：
1. 模块集成测试通过
2. 端到端测试通过
3. 性能指标达标
4. 代码审查通过

---

## 五、文档要求

### 5.1 代码文档

- 所有公共函数必须有docstring
- 复杂逻辑必须有注释
- 使用类型注解（Type Hints）

### 5.2 API文档

- 更新OpenAPI文档
- 添加请求/响应示例

### 5.3 运维文档

- 更新 `docs/OPERATIONS.md`
- 添加场景测试配置说明
- 添加AI决策调优指南

---

## 六、风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| AI服务不稳定 | 高 | 中 | 实现降级策略，使用规则引擎备份 |
| 模拟器资源不足 | 高 | 中 | 动态扩容机制，任务队列限流 |
| 协议解析复杂 | 中 | 低 | 渐进式实现，优先支持常见协议 |
| 测试数据准备困难 | 中 | 中 | 使用Mock数据，避免真实交易 |

---

## 七、时间线

| 周 | 任务 | 交付物 |
|----|------|--------|
| 第1周 | 任务2.1 | 静态分析功能集成 |
| 第2-3周 | 任务2.2 | 动态分析场景扩展 |
| 第3-4周 | 任务2.3 | AI决策优化 |
| 第4周 | 任务2.4 | 流量监控增强 |

---

**文档维护者**: 技术架构团队
**最后更新**: 2026-02-21
**审批状态**: 待审批
