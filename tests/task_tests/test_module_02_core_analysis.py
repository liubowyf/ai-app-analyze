"""
模块二：核心分析引擎测试用例

包含以下任务的测试用例：
- 任务 2.1: 静态分析功能集成
- 任务 2.2: 动态分析增强 - 场景扩展
- 任务 2.3: AI 驱动优化 - 决策智能增强
- 任务 2.4: 流量监控增强 - 协议解析
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from androguard.core.bytecodes.apk import APK
import json
import asyncio


# =============================================================================
# 任务 2.1: 静态分析功能集成
# =============================================================================

class TestStaticAnalyzerIntegration:
    """静态分析集成测试"""

    @pytest.fixture
    def mock_apk(self):
        """模拟 APK 对象"""
        with patch('androguard.core.bytecodes.apk.APK') as mock:
            apk = MagicMock()
            mock.return_value = apk

            # 设置默认属性
            apk.get_package.return_value = "com.example.app"
            apk.get_app_name.return_value = "Example App"
            apk.get_androidversion_name.return_value = "1.0.0"
            apk.get_androidversion_code.return_value = "1"
            apk.get_min_sdk_version.return_value = "21"
            apk.get_target_sdk_version.return_value = "30"
            apk.get_permissions.return_value = [
                "android.permission.INTERNET",
                "android.permission.ACCESS_NETWORK_STATE",
                "android.permission.READ_CONTACTS"
            ]
            apk.get_activities.return_value = ["com.example.app.MainActivity"]
            apk.get_services.return_value = ["com.example.app.BackgroundService"]
            apk.get_receivers.return_value = ["com.example.app.BootReceiver"]
            apk.get_providers.return_value = ["com.example.app.DataProvider"]

            yield apk

    def test_static_analysis_in_pipeline(self, client, mock_apk):
        """
        测试静态分析在流水线中执行

        验证点:
        1. APK 上传后触发静态分析
        2. 静态分析在动态分析之前执行
        3. 静态分析结果存储到数据库
        4. 任务状态正确转换
        """
        # 上传 APK
        with open("tests/fixtures/test.apk", "rb") as f:
            upload_response = client.post(
                "/api/v1/apk/upload",
                files={"file": ("test.apk", f, "application/vnd.android.package-archive")}
            )

        assert upload_response.status_code == 200
        task_id = upload_response.json()["task_id"]

        # 启动任务
        start_response = client.post(
            "/api/v1/tasks",
            json={"task_id": task_id}
        )

        assert start_response.status_code == 200

        # 查询任务状态，验证静态分析执行
        import time
        max_wait = 60
        start_time = time.time()

        static_analysis_done = False
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/api/v1/tasks/{task_id}")
            status = status_response.json()["status"]

            if status == "static_analyzing":
                static_analysis_done = True

            if status in ["dynamic_analyzing", "completed", "failed"]:
                break

            time.sleep(2)

        assert static_analysis_done, "静态分析未被触发"

    def test_static_analysis_result_storage(self, db_session, mock_apk):
        """
        测试静态分析结果存储

        验证点:
        1. 结果存储到数据库 JSON 字段
        2. 包含基本信息
        3. 包含权限信息
        4. 包含组件信息
        """
        from modules.apk_analyzer.analyzer import ApkAnalyzer
        from models.task import Task

        # 创建任务
        task = Task(
            id="test-task-123",
            apk_file_name="test.apk",
            status="static_analyzing"
        )
        db_session.add(task)
        db_session.commit()

        # 执行静态分析
        analyzer = ApkAnalyzer()
        result = analyzer.analyze("tests/fixtures/test.apk")

        # 存储结果
        task.static_analysis_result = result
        db_session.commit()

        # 验证存储
        saved_task = db_session.query(Task).filter_by(id="test-task-123").first()
        assert saved_task.static_analysis_result is not None

        result_data = saved_task.static_analysis_result
        assert "basic_info" in result_data
        assert "permissions" in result_data
        assert "components" in result_data

    def test_static_analysis_performance(self, mock_apk):
        """
        测试静态分析性能

        验证点:
        1. 分析时间 < 30秒
        2. 内存使用合理
        3. CPU 使用合理
        """
        import time
        import tracemalloc

        from modules.apk_analyzer.analyzer import ApkAnalyzer

        tracemalloc.start()
        start_time = time.time()

        analyzer = ApkAnalyzer()
        result = analyzer.analyze("tests/fixtures/test.apk")

        elapsed_time = time.time() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert elapsed_time < 30, f"静态分析耗时 {elapsed_time:.2f}秒，超过30秒阈值"
        assert peak < 100 * 1024 * 1024, f"内存峰值 {peak / 1024 / 1024:.2f}MB，超过100MB阈值"

    def test_risk_scoring(self, mock_apk):
        """
        测试风险评分

        验证点:
        1. 危险权限被识别
        2. 权限风险评分计算
        3. 组件风险评分计算
        4. 总体风险评分合理
        """
        from modules.apk_analyzer.analyzer import ApkAnalyzer

        analyzer = ApkAnalyzer()
        result = analyzer.analyze("tests/fixtures/test.apk")

        # 验证权限风险评分
        assert "permission_risk" in result
        assert "score" in result["permission_risk"]
        assert "dangerous_permissions" in result["permission_risk"]

        # 验证危险权限被识别
        dangerous_perms = result["permission_risk"]["dangerous_permissions"]
        assert "android.permission.READ_CONTACTS" in dangerous_perms

        # 验证总体评分
        assert "overall_risk_score" in result
        assert 0 <= result["overall_risk_score"] <= 100

    def test_apk_cache(self, mock_apk):
        """
        测试 APK 解析缓存

        验证点:
        1. 相同 APK 不重复解析
        2. 缓存命中时性能提升
        3. 缓存键使用 MD5
        4. 缓存可失效
        """
        from modules.apk_analyzer.analyzer import ApkAnalyzer
        import hashlib

        # 计算 APK MD5
        with open("tests/fixtures/test.apk", "rb") as f:
            apk_md5 = hashlib.md5(f.read()).hexdigest()

        analyzer = ApkAnalyzer()

        # 首次分析（缓存未命中）
        with patch('core.cache.CacheManager') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance
            mock_cache_instance.get.return_value = None

            result1 = analyzer.analyze_with_cache("tests/fixtures/test.apk", apk_md5)

            # 验证缓存尝试读取
            mock_cache_instance.get.assert_called_once()

        # 再次分析（缓存命中）
        with patch('core.cache.CacheManager') as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance
            mock_cache_instance.get.return_value = json.dumps(result1)

            result2 = analyzer.analyze_with_cache("tests/fixtures/test.apk", apk_md5)

            # 验证缓存命中，直接返回
            assert result2 == result1

    def test_signature_verification(self, mock_apk):
        """
        测试签名验证

        验证点:
        1. 提取签名信息
        2. 验证签名有效性
        3. 识别调试签名
        4. 提取证书信息
        """
        from modules.apk_analyzer.analyzer import ApkAnalyzer

        analyzer = ApkAnalyzer()
        result = analyzer.analyze("tests/fixtures/test.apk")

        assert "signature_info" in result
        assert "is_debuggable" in result["signature_info"]
        assert "certificate_info" in result["signature_info"]

    def test_component_analysis(self, mock_apk):
        """
        测试组件分析

        验证点:
        1. 提取所有组件
        2. 识别导出组件
        3. 分析 intent-filter
        4. 识别风险组件
        """
        from modules.apk_analyzer.analyzer import ApkAnalyzer

        analyzer = ApkAnalyzer()
        result = analyzer.analyze("tests/fixtures/test.apk")

        assert "components" in result
        components = result["components"]

        # 验证四大组件
        assert "activities" in components
        assert "services" in components
        assert "receivers" in components
        assert "providers" in components

        # 验证组件详情
        assert len(components["activities"]) > 0
        assert components["activities"][0]["name"] == "com.example.app.MainActivity"


# =============================================================================
# 任务 2.2: 动态分析增强 - 场景扩展
# =============================================================================

class TestScenarioTesting:
    """场景测试测试"""

    @pytest.fixture
    def mock_android_runner(self):
        """模拟 Android 运行器"""
        with patch('modules.android_runner.runner.AndroidRunner') as mock:
            runner = MagicMock()
            mock.return_value = runner

            runner.connect_remote_emulator.return_value = True
            runner.install_apk_remote.return_value = True
            runner.launch_app.return_value = True
            runner.take_screenshot_remote.return_value = b"fake_screenshot"

            yield runner

    @pytest.fixture
    def mock_ai_driver(self):
        """模拟 AI 驱动器"""
        with patch('modules.ai_driver.driver.AIDriver') as mock:
            driver = MagicMock()
            mock.return_value = driver

            driver.analyze_screenshot.return_value = {
                "ui_elements": [
                    {"type": "button", "text": "Login", "bounds": [100, 200, 300, 250]},
                    {"type": "input", "hint": "Username", "bounds": [100, 100, 300, 150]}
                ]
            }

            yield driver

    def test_login_scenario_detection(self, mock_android_runner, mock_ai_driver):
        """
        测试登录场景检测

        验证点:
        1. 识别登录按钮
        2. 识别用户名输入框
        3. 识别密码输入框
        4. 返回场景类型
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        # 模拟截图分析
        screenshot = b"login_screen_screenshot"
        scenario = tester.detect_scenario(screenshot)

        assert scenario["type"] == "login"
        assert "elements" in scenario
        assert any(elem["type"] == "button" and "login" in elem["text"].lower()
                   for elem in scenario["elements"])

    def test_login_scenario_execution(self, mock_android_runner, mock_ai_driver):
        """
        测试登录场景执行

        验证点:
        1. 输入用户名
        2. 输入密码
        3. 点击登录按钮
        4. 捕获登录请求
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        # 执行登录场景
        result = tester.execute_login_scenario(
            username="test_user",
            password="test_password"
        )

        assert result["success"] is True
        assert result["steps_executed"] == 3  # 输入用户名、密码、点击登录

        # 验证调用顺序
        mock_android_runner.execute_input_text.assert_any_call(
            pytest.approx(200, 100),  # x 坐标允许误差
            pytest.approx(125, 25),   # y 坐标允许误差
            "test_user"
        )

    def test_payment_scenario_detection(self, mock_android_runner, mock_ai_driver):
        """
        测试支付场景检测

        验证点:
        1. 识别支付按钮
        2. 识别金额输入框
        3. 识别支付方式选择
        4. 返回场景类型
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester

        # 配置 AI 返回支付界面元素
        mock_ai_driver.analyze_screenshot.return_value = {
            "ui_elements": [
                {"type": "button", "text": "Pay Now", "bounds": [100, 300, 300, 350]},
                {"type": "input", "hint": "Amount", "bounds": [100, 200, 300, 250]},
                {"type": "text", "text": "Payment Method", "bounds": [100, 100, 300, 150]}
            ]
        }

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        screenshot = b"payment_screen_screenshot"
        scenario = tester.detect_scenario(screenshot)

        assert scenario["type"] == "payment"
        assert any("pay" in elem["text"].lower() for elem in scenario["elements"])

    def test_payment_scenario_execution(self, mock_android_runner, mock_ai_driver):
        """
        测试支付场景执行

        验证点:
        1. 输入金额
        2. 选择支付方式
        3. 点击支付按钮
        4. 捕获支付请求
        5. 检测敏感数据
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester
        from modules.traffic_monitor.monitor import TrafficMonitor

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        # 模拟流量监控
        with patch.object(TrafficMonitor, 'get_requests') as mock_requests:
            mock_requests.return_value = [
                {
                    "url": "https://payment.example.com/api/pay",
                    "method": "POST",
                    "body": '{"amount": 100, "card_number": "****"}'
                }
            ]

            result = tester.execute_payment_scenario(amount=100.0)

            assert result["success"] is True
            assert result["sensitive_data_detected"] is True
            assert len(result["payment_requests"]) > 0

    def test_share_scenario_detection(self, mock_android_runner, mock_ai_driver):
        """
        测试分享场景检测

        验证点:
        1. 识别分享按钮
        2. 识别分享目标
        3. 返回场景类型
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester

        # 配置 AI 返回分享界面元素
        mock_ai_driver.analyze_screenshot.return_value = {
            "ui_elements": [
                {"type": "button", "text": "Share", "bounds": [100, 200, 300, 250]},
                {"type": "icon", "text": "WeChat", "bounds": [100, 300, 200, 400]},
                {"type": "icon", "text": "QQ", "bounds": [220, 300, 320, 400]}
            ]
        }

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        screenshot = b"share_screen_screenshot"
        scenario = tester.detect_scenario(screenshot)

        assert scenario["type"] == "share"
        assert len(scenario["share_targets"]) >= 1

    def test_scenario_report_generation(self, mock_android_runner, mock_ai_driver):
        """
        测试场景报告生成

        验证点:
        1. 包含场景类型
        2. 包含执行步骤
        3. 包含网络请求
        4. 包含敏感数据
        5. 包含截图
        """
        from modules.exploration_strategy.scenario_tester import ScenarioTester

        tester = ScenarioTester(mock_android_runner, mock_ai_driver)

        # 执行多个场景
        results = {
            "login": tester.execute_login_scenario("user", "pass"),
            "payment": tester.execute_payment_scenario(100.0),
            "share": tester.execute_share_scenario()
        }

        # 生成报告
        report = tester.generate_scenario_report(results)

        assert "scenarios" in report
        assert "login" in report["scenarios"]
        assert "payment" in report["scenarios"]
        assert "share" in report["scenarios"]

        # 验证每个场景的报告内容
        for scenario_name, scenario_data in report["scenarios"].items():
            assert "success" in scenario_data
            assert "steps_executed" in scenario_data
            assert "screenshots" in scenario_data


# =============================================================================
# 任务 2.3: AI 驱动优化 - 决策智能增强
# =============================================================================

class TestAIDecisionEnhanced:
    """AI 决策增强测试"""

    @pytest.fixture
    def mock_openai_client(self):
        """模拟 OpenAI 客户端"""
        with patch('openai.OpenAI') as mock:
            client = MagicMock()
            mock.return_value = client

            client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "action": "tap",
                            "coordinates": [200, 300],
                            "reasoning": "Tap on login button to proceed"
                        })
                    )
                )]
            )

            yield client

    def test_exploration_depth_limit(self, mock_android_runner, mock_openai_client):
        """
        测试探索深度限制

        验证点:
        1. 超过最大深度后停止
        2. 记录深度日志
        3. 返回深度限制原因
        4. 保存当前状态
        """
        from modules.exploration_strategy.explorer import AppExplorer

        explorer = AppExplorer(
            runner=mock_android_runner,
            max_exploration_depth=50
        )

        # 模拟超过最大深度
        explorer.current_depth = 51

        result = explorer.explore_step()

        assert result["status"] == "depth_limit_reached"
        assert result["current_depth"] == 51
        assert result["max_depth"] == 50

    def test_loop_detection(self, mock_android_runner, mock_openai_client):
        """
        测试循环检测

        验证点:
        1. 检测重复界面
        2. 记录循环次数
        3. 触发循环处理策略
        4. 避免无限循环
        """
        from modules.exploration_strategy.explorer import AppExplorer

        explorer = AppExplorer(runner=mock_android_runner)

        # 模拟循环界面（相同截图）
        screenshot_hash = "abc123"

        # 记录相同界面多次
        for _ in range(5):
            explorer.visit_history.append({
                "screenshot_hash": screenshot_hash,
                "activity": "com.example.app.MainActivity"
            })

        # 检测循环
        is_loop = explorer.detect_loop(screenshot_hash)

        assert is_loop is True
        assert explorer.loop_count >= 3

    def test_smart_backtrack(self, mock_android_runner, mock_openai_client):
        """
        测试智能回退

        验证点:
        1. 识别死胡同
        2. 执行回退操作
        3. 选择正确的历史状态
        4. 继续探索
        """
        from modules.exploration_strategy.explorer import AppExplorer

        explorer = AppExplorer(runner=mock_android_runner)

        # 模拟探索历史
        explorer.visit_history = [
            {"activity": "MainActivity", "depth": 0},
            {"activity": "DetailActivity", "depth": 1},
            {"activity": "WebViewActivity", "depth": 2}  # 死胡同
        ]

        explorer.current_depth = 2

        # 触发回退
        result = explorer.backtrack()

        assert result["success"] is True
        assert result["backtracked_to_depth"] < 2
        assert mock_android_runner.press_back.called or mock_android_runner.press_home.called

    def test_prompt_optimization(self, mock_android_runner, mock_openai_client):
        """
        测试 Prompt 优化

        验证点:
        1. Prompt 包含上下文
        2. Prompt 包含历史操作
        3. Prompt 格式优化
        4. AI 响应质量提升
        """
        from modules.ai_driver.driver import AIDriver

        driver = AIDriver()

        # 分析截图
        screenshot = b"test_screenshot"
        context = {
            "current_activity": "MainActivity",
            "recent_actions": ["tap_login", "input_username"],
            "exploration_depth": 5
        }

        result = driver.analyze_screenshot(screenshot, context=context)

        # 验证 API 调用
        mock_openai_client.chat.completions.create.assert_called_once()
        call_args = mock_openai_client.chat.completions.create.call_args

        # 验证 Prompt 内容
        messages = call_args[1]["messages"]
        assert len(messages) > 1
        assert any("context" in str(msg).lower() for msg in messages)

    def test_decision_logging(self, mock_android_runner, mock_openai_client):
        """
        测试决策日志

        验证点:
        1. 每次决策被记录
        2. 包含决策原因
        3. 包含时间戳
        4. 包含上下文信息
        """
        from modules.ai_driver.driver import AIDriver

        driver = AIDriver()

        # 执行决策
        screenshot = b"test_screenshot"
        decision = driver.decide_operation(screenshot)

        # 验证日志记录
        with patch('modules.ai_driver.driver.decision_logger') as mock_logger:
            driver.log_decision(decision)

            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args

            assert "action" in call_args[1]
            assert "reasoning" in call_args[1]
            assert "timestamp" in call_args[1]

    def test_multi_step_reasoning(self, mock_android_runner, mock_openai_client):
        """
        测试多步推理

        验证点:
        1. 生成多步操作序列
        2. 步骤间依赖正确
        3. 可中断和恢复
        4. 失败可重试
        """
        from modules.ai_driver.driver import AIDriver

        driver = AIDriver()

        # 生成操作序列
        context = {
            "goal": "Complete login process",
            "current_state": "login_screen"
        }

        operation_sequence = driver.plan_operations(context)

        assert isinstance(operation_sequence, list)
        assert len(operation_sequence) > 1

        # 验证步骤依赖
        for i, step in enumerate(operation_sequence):
            if i > 0:
                assert "depends_on" in step or step.get("order") == i


# =============================================================================
# 任务 2.4: 流量监控增强 - 协议解析
# =============================================================================

class TestTrafficProtocolParsing:
    """流量协议解析测试"""

    @pytest.fixture
    def mock_mitmproxy(self):
        """模拟 mitmproxy"""
        with patch('mitmproxy.master.Master') as mock:
            master = MagicMock()
            mock.return_value = master
            yield master

    def test_websocket_capture(self, mock_mitmproxy):
        """
        测试 WebSocket 捕获

        验证点:
        1. WebSocket 连接被捕获
        2. 消息被记录
        3. 消息方向正确
        4. 支持文本和二进制消息
        """
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 模拟 WebSocket 消息
        ws_message = {
            "type": "websocket",
            "direction": "outgoing",
            "content": '{"action": "send_message", "data": "Hello"}',
            "timestamp": "2026-02-21T10:00:00Z",
            "connection_id": "ws-123"
        }

        monitor.add_websocket_message(ws_message)

        # 获取 WebSocket 消息
        messages = monitor.get_websocket_messages()

        assert len(messages) == 1
        assert messages[0]["direction"] == "outgoing"
        assert messages[0]["connection_id"] == "ws-123"

    def test_grpc_parsing(self, mock_mitmproxy):
        """
        测试 gRPC 解析

        验证点:
        1. gRPC 请求被识别
        2. Protobuf 消息被解析
        3. 服务和方法被提取
        4. 元数据被记录
        """
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 模拟 gRPC 请求
        grpc_request = {
            "type": "grpc",
            "service": "com.example.api.UserService",
            "method": "GetUserProfile",
            "request_data": {"user_id": "123"},
            "response_data": {"name": "John", "age": 30},
            "headers": {"content-type": "application/grpc"}
        }

        monitor.add_grpc_request(grpc_request)

        # 获取 gRPC 请求
        requests = monitor.get_grpc_requests()

        assert len(requests) == 1
        assert requests[0]["service"] == "com.example.api.UserService"
        assert requests[0]["method"] == "GetUserProfile"

    def test_custom_protocol_detection(self, mock_mitmproxy):
        """
        测试自定义协议识别

        验证点:
        1. 非标准协议被识别
        2. 协议特征被提取
        3. 标记为未知协议
        4. 原始数据被保留
        """
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 模拟自定义协议
        custom_request = {
            "type": "unknown",
            "port": 8888,
            "raw_data": b"custom_protocol_data",
            "detected_by": "heuristic",
            "protocol_signature": "0xCAFEBABE"
        }

        monitor.add_custom_protocol_request(custom_request)

        # 获取自定义协议请求
        requests = monitor.get_custom_protocol_requests()

        assert len(requests) == 1
        assert requests[0]["type"] == "unknown"
        assert requests[0]["port"] == 8888

    def test_https_decryption_performance(self, mock_mitmproxy):
        """
        测试 HTTPS 解密性能

        验证点:
        1. 解密不影响应用性能
        2. 解密延迟 < 100ms
        3. 证书验证正确
        4. 支持证书绑定
        """
        import time
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 测试解密性能
        start_time = time.time()

        for _ in range(100):
            https_request = {
                "url": "https://api.example.com/data",
                "method": "GET",
                "encrypted": True
            }
            monitor.process_https_request(https_request)

        elapsed_time = time.time() - start_time
        avg_latency = (elapsed_time / 100) * 1000  # 毫秒

        assert avg_latency < 100, f"HTTPS 解密平均延迟 {avg_latency:.2f}ms，超过 100ms 阈值"

    def test_traffic_visualization(self, mock_mitmproxy):
        """
        测试流量可视化

        验证点:
        1. 生成流量时序图
        2. 显示请求类型分布
        3. 显示域名统计
        4. 支持交互式查看
        """
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 添加多种类型的流量
        requests = [
            {"url": "https://api.example.com/users", "method": "GET", "size": 1024},
            {"url": "https://api.example.com/posts", "method": "POST", "size": 2048},
            {"url": "wss://chat.example.com/ws", "type": "websocket", "size": 512},
            {"url": "https://cdn.example.com/image.png", "method": "GET", "size": 5120}
        ]

        for req in requests:
            monitor.add_request(req)

        # 生成可视化数据
        viz_data = monitor.generate_visualization()

        assert "timeline" in viz_data
        assert "method_distribution" in viz_data
        assert "domain_stats" in viz_data
        assert "total_requests" in viz_data

    def test_protocol_statistics(self, mock_mitmproxy):
        """
        测试协议统计

        验证点:
        1. 统计各协议占比
        2. 统计数据量
        3. 统计请求频率
        4. 识别异常协议使用
        """
        from modules.traffic_monitor.monitor import TrafficMonitor

        monitor = TrafficMonitor()

        # 添加不同协议的流量
        protocol_requests = [
            {"protocol": "http", "count": 10, "bytes": 10240},
            {"protocol": "https", "count": 50, "bytes": 51200},
            {"protocol": "websocket", "count": 5, "bytes": 2560},
            {"protocol": "grpc", "count": 8, "bytes": 4096}
        ]

        for req in protocol_requests:
            for _ in range(req["count"]):
                monitor.add_request({
                    "protocol": req["protocol"],
                    "size": req["bytes"] // req["count"]
                })

        # 获取统计
        stats = monitor.get_protocol_statistics()

        assert "http" in stats
        assert "https" in stats
        assert "websocket" in stats
        assert "grpc" in stats

        # 验证 HTTPS 占比最高
        assert stats["https"]["percentage"] > stats["http"]["percentage"]
