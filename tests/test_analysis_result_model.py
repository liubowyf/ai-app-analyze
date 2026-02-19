"""Unit tests for Analysis Result models."""
from datetime import datetime

import pytest
from pydantic import ValidationError

from models.analysis_result import (
    AnalysisResult,
    ApkBasicInfo,
    ComponentInfo,
    DynamicAnalysisResult,
    NetworkRequest,
    PermissionInfo,
    RiskLevel,
    Screenshot,
    SensitiveApiCall,
    StaticAnalysisResult,
)


class TestRiskLevel:
    """Test cases for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test that RiskLevel has all required values."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"


class TestPermissionInfo:
    """Test cases for PermissionInfo model."""

    def test_create_permission_info_with_required_fields(self):
        """Test creating PermissionInfo with only required fields."""
        permission = PermissionInfo(
            name="android.permission.INTERNET",
            protection_level="normal",
            description="Allows network access",
        )

        assert permission.name == "android.permission.INTERNET"
        assert permission.protection_level == "normal"
        assert permission.description == "Allows network access"
        assert permission.risk_level == RiskLevel.LOW
        assert permission.risk_reason is None

    def test_create_permission_info_with_all_fields(self):
        """Test creating PermissionInfo with all fields."""
        permission = PermissionInfo(
            name="android.permission.READ_CONTACTS",
            protection_level="dangerous",
            description="Read contacts",
            risk_level=RiskLevel.HIGH,
            risk_reason="Can access sensitive user data",
        )

        assert permission.name == "android.permission.READ_CONTACTS"
        assert permission.protection_level == "dangerous"
        assert permission.description == "Read contacts"
        assert permission.risk_level == RiskLevel.HIGH
        assert permission.risk_reason == "Can access sensitive user data"

    def test_permission_info_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            PermissionInfo(name="test.permission")


class TestComponentInfo:
    """Test cases for ComponentInfo model."""

    def test_create_component_info_with_required_fields(self):
        """Test creating ComponentInfo with only required fields."""
        component = ComponentInfo(
            component_type="activity",
            component_name="com.example.MainActivity",
            is_exported=True,
        )

        assert component.component_type == "activity"
        assert component.component_name == "com.example.MainActivity"
        assert component.is_exported is True
        assert component.intent_filters == []
        assert component.risk_level == RiskLevel.LOW

    def test_create_component_info_with_all_fields(self):
        """Test creating ComponentInfo with all fields."""
        component = ComponentInfo(
            component_type="receiver",
            component_name="com.example.BootReceiver",
            is_exported=True,
            intent_filters=["android.intent.action.BOOT_COMPLETED"],
            risk_level=RiskLevel.HIGH,
        )

        assert component.component_type == "receiver"
        assert component.component_name == "com.example.BootReceiver"
        assert component.is_exported is True
        assert component.intent_filters == ["android.intent.action.BOOT_COMPLETED"]
        assert component.risk_level == RiskLevel.HIGH


class TestApkBasicInfo:
    """Test cases for ApkBasicInfo model."""

    def test_create_apk_basic_info_with_required_fields(self):
        """Test creating ApkBasicInfo with only required fields."""
        basic_info = ApkBasicInfo(
            package_name="com.example.app",
            app_name="Example App",
            version_name="1.0.0",
            version_code=1,
            file_size=1024000,
            md5="abc123def456",
            sha256="sha256hash123456",
        )

        assert basic_info.package_name == "com.example.app"
        assert basic_info.app_name == "Example App"
        assert basic_info.version_name == "1.0.0"
        assert basic_info.version_code == 1
        assert basic_info.file_size == 1024000
        assert basic_info.md5 == "abc123def456"
        assert basic_info.sha256 == "sha256hash123456"
        assert basic_info.min_sdk is None
        assert basic_info.target_sdk is None
        assert basic_info.signature is None
        assert basic_info.is_debuggable is False
        assert basic_info.is_packed is False
        assert basic_info.packer_name is None

    def test_create_apk_basic_info_with_all_fields(self):
        """Test creating ApkBasicInfo with all fields."""
        basic_info = ApkBasicInfo(
            package_name="com.test.app",
            app_name="Test App",
            version_name="2.0.0",
            version_code=2,
            min_sdk=21,
            target_sdk=33,
            file_size=2048000,
            md5="testmd5hash",
            sha256="testsha256hash",
            signature="testsignature",
            is_debuggable=True,
            is_packed=True,
            packer_name="UPX",
        )

        assert basic_info.min_sdk == 21
        assert basic_info.target_sdk == 33
        assert basic_info.signature == "testsignature"
        assert basic_info.is_debuggable is True
        assert basic_info.is_packed is True
        assert basic_info.packer_name == "UPX"


class TestStaticAnalysisResult:
    """Test cases for StaticAnalysisResult model."""

    def test_create_static_analysis_result_with_required_fields(self):
        """Test creating StaticAnalysisResult with only required fields."""
        result = StaticAnalysisResult(basic_info=ApkBasicInfo(
            package_name="com.example.app",
            app_name="Example",
            version_name="1.0",
            version_code=1,
            file_size=1024,
            md5="md5hash",
            sha256="sha256hash",
        ))

        assert result.basic_info.package_name == "com.example.app"
        assert result.permissions == []
        assert result.components == []
        assert result.native_libraries == []
        assert result.suspicious_apis == []
        assert result.analysis_time is not None

    def test_create_static_analysis_result_with_all_fields(self):
        """Test creating StaticAnalysisResult with all fields."""
        basic_info = ApkBasicInfo(
            package_name="com.test.app",
            app_name="Test",
            version_name="1.0",
            version_code=1,
            file_size=2048,
            md5="testmd5",
            sha256="testsha256",
        )
        permissions = [
            PermissionInfo(name="android.permission.INTERNET", protection_level="normal", description="Network"),
        ]
        components = [
            ComponentInfo(component_type="activity", component_name="MainActivity", is_exported=False),
        ]

        analysis_time = datetime.utcnow()
        result = StaticAnalysisResult(
            basic_info=basic_info,
            permissions=permissions,
            components=components,
            native_libraries=["libtest.so"],
            suspicious_apis=["getDeviceId"],
            analysis_time=analysis_time,
        )

        assert len(result.permissions) == 1
        assert len(result.components) == 1
        assert result.native_libraries == ["libtest.so"]
        assert result.suspicious_apis == ["getDeviceId"]
        assert result.analysis_time == analysis_time


class TestNetworkRequest:
    """Test cases for NetworkRequest model."""

    def test_create_network_request_with_required_fields(self):
        """Test creating NetworkRequest with only required fields."""
        request = NetworkRequest(
            request_id="req-001",
            url="https://example.com/api",
            domain="example.com",
            ip="192.168.1.1",
            port=443,
            method="GET",
            is_https=True,
            request_time=datetime.utcnow(),
        )

        assert request.request_id == "req-001"
        assert request.url == "https://example.com/api"
        assert request.domain == "example.com"
        assert request.ip == "192.168.1.1"
        assert request.port == 443
        assert request.method == "GET"
        assert request.is_https is True
        assert request.response_code is None
        assert request.content_type is None
        assert request.is_whitelisted is False
        assert request.whitelist_category is None
        assert request.risk_level == RiskLevel.LOW
        assert request.risk_reason is None

    def test_create_network_request_with_all_fields(self):
        """Test creating NetworkRequest with all fields."""
        request_time = datetime.utcnow()
        request = NetworkRequest(
            request_id="req-002",
            url="http://malicious.com/data",
            domain="malicious.com",
            ip="10.0.0.1",
            port=80,
            method="POST",
            is_https=False,
            request_time=request_time,
            response_code=200,
            content_type="application/json",
            is_whitelisted=True,
            whitelist_category="trusted",
            risk_level=RiskLevel.HIGH,
            risk_reason="Non-HTTPS connection to unknown domain",
        )

        assert request.response_code == 200
        assert request.content_type == "application/json"
        assert request.is_whitelisted is True
        assert request.whitelist_category == "trusted"
        assert request.risk_level == RiskLevel.HIGH


class TestSensitiveApiCall:
    """Test cases for SensitiveApiCall model."""

    def test_create_sensitive_api_call_with_required_fields(self):
        """Test creating SensitiveApiCall with only required fields."""
        api_call = SensitiveApiCall(
            api_name="getDeviceId",
            api_class="android.telephony.TelephonyManager",
            call_count=5,
            first_call_time=datetime.utcnow(),
            last_call_time=datetime.utcnow(),
        )

        assert api_call.api_name == "getDeviceId"
        assert api_call.api_class == "android.telephony.TelephonyManager"
        assert api_call.call_count == 5
        assert api_call.risk_level == RiskLevel.LOW
        assert api_call.description is None

    def test_create_sensitive_api_call_with_all_fields(self):
        """Test creating SensitiveApiCall with all fields."""
        api_call = SensitiveApiCall(
            api_name="exec",
            api_class="java.lang.Runtime",
            call_count=10,
            first_call_time=datetime.utcnow(),
            last_call_time=datetime.utcnow(),
            risk_level=RiskLevel.CRITICAL,
            description="Execute shell commands",
        )

        assert api_call.risk_level == RiskLevel.CRITICAL
        assert api_call.description == "Execute shell commands"


class TestScreenshot:
    """Test cases for Screenshot model."""

    def test_create_screenshot_with_required_fields(self):
        """Test creating Screenshot with only required fields."""
        screenshot = Screenshot(
            screenshot_id="scr-001",
            step_number=1,
            operation_type="click",
            operation_detail="Click login button",
            screenshot_path="/screenshots/scr-001.png",
            capture_time=datetime.utcnow(),
        )

        assert screenshot.screenshot_id == "scr-001"
        assert screenshot.step_number == 1
        assert screenshot.operation_type == "click"
        assert screenshot.operation_detail == "Click login button"
        assert screenshot.screenshot_path == "/screenshots/scr-001.png"
        assert screenshot.ai_description is None

    def test_create_screenshot_with_all_fields(self):
        """Test creating Screenshot with all fields."""
        screenshot = Screenshot(
            screenshot_id="scr-002",
            step_number=2,
            operation_type="input",
            operation_detail="Enter username",
            screenshot_path="/screenshots/scr-002.png",
            capture_time=datetime.utcnow(),
            ai_description="Login form with username field highlighted",
        )

        assert screenshot.ai_description == "Login form with username field highlighted"


class TestDynamicAnalysisResult:
    """Test cases for DynamicAnalysisResult model."""

    def test_create_dynamic_analysis_result_with_required_fields(self):
        """Test creating DynamicAnalysisResult with only required fields."""
        result = DynamicAnalysisResult(
            analysis_duration_seconds=300,
        )

        assert result.network_requests == []
        assert result.sensitive_api_calls == []
        assert result.screenshots == []
        assert result.analysis_duration_seconds == 300
        assert result.analysis_time is not None

    def test_create_dynamic_analysis_result_with_all_fields(self):
        """Test creating DynamicAnalysisResult with all fields."""
        network_request = NetworkRequest(
            request_id="req-001",
            url="https://example.com",
            domain="example.com",
            ip="192.168.1.1",
            port=443,
            method="GET",
            is_https=True,
            request_time=datetime.utcnow(),
        )
        api_call = SensitiveApiCall(
            api_name="getDeviceId",
            api_class="android.telephony.TelephonyManager",
            call_count=1,
            first_call_time=datetime.utcnow(),
            last_call_time=datetime.utcnow(),
        )
        screenshot = Screenshot(
            screenshot_id="scr-001",
            step_number=1,
            operation_type="launch",
            operation_detail="App launch",
            screenshot_path="/screenshots/scr-001.png",
            capture_time=datetime.utcnow(),
        )

        result = DynamicAnalysisResult(
            network_requests=[network_request],
            sensitive_api_calls=[api_call],
            screenshots=[screenshot],
            analysis_duration_seconds=600,
            analysis_time=datetime.utcnow(),
        )

        assert len(result.network_requests) == 1
        assert len(result.sensitive_api_calls) == 1
        assert len(result.screenshots) == 1


class TestAnalysisResult:
    """Test cases for AnalysisResult model."""

    def test_create_analysis_result_with_required_fields(self):
        """Test creating AnalysisResult with only required fields."""
        task_id = "task-123"
        result = AnalysisResult(task_id=task_id)

        assert result.task_id == task_id
        assert result.static_analysis is None
        assert result.dynamic_analysis is None
        assert result.overall_risk_level == RiskLevel.LOW
        assert result.risk_points == []
        assert result.recommendations == []
        assert result.analysis_time is not None

    def test_create_analysis_result_with_all_fields(self):
        """Test creating AnalysisResult with all fields."""
        static_result = StaticAnalysisResult(
            basic_info=ApkBasicInfo(
                package_name="com.example.app",
                app_name="Example",
                version_name="1.0",
                version_code=1,
                file_size=1024,
                md5="md5hash",
                sha256="sha256hash",
            )
        )
        dynamic_result = DynamicAnalysisResult(analysis_duration_seconds=300)

        result = AnalysisResult(
            task_id="task-456",
            static_analysis=static_result,
            dynamic_analysis=dynamic_result,
            overall_risk_level=RiskLevel.HIGH,
            risk_points=["Dangerous permission: READ_CONTACTS", "Unencrypted network traffic"],
            recommendations=["Remove unnecessary permissions", "Use HTTPS for all network calls"],
            analysis_time=datetime.utcnow(),
        )

        assert result.task_id == "task-456"
        assert result.static_analysis is not None
        assert result.dynamic_analysis is not None
        assert result.overall_risk_level == RiskLevel.HIGH
        assert len(result.risk_points) == 2
        assert len(result.recommendations) == 2

    def test_analysis_result_model_dump(self):
        """Test that AnalysisResult can be serialized to dict."""
        result = AnalysisResult(
            task_id="task-789",
            overall_risk_level=RiskLevel.MEDIUM,
            risk_points=["Test risk"],
            recommendations=["Test recommendation"],
        )

        result_dict = result.model_dump()

        assert result_dict["task_id"] == "task-789"
        assert result_dict["overall_risk_level"] == RiskLevel.MEDIUM
        assert result_dict["risk_points"] == ["Test risk"]
        assert result_dict["recommendations"] == ["Test recommendation"]
        assert "analysis_time" in result_dict
