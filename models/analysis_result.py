"""Analysis result models for APK analysis."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level enum for analysis results."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionInfo(BaseModel):
    """
    Permission information model.

    Attributes:
        name: Permission name (e.g., android.permission.INTERNET)
        protection_level: Protection level (normal, dangerous, signature, etc.)
        description: Permission description
        risk_level: Risk level assessment
        risk_reason: Reason for the risk assessment
    """

    name: str
    protection_level: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    risk_reason: Optional[str] = None


class ComponentInfo(BaseModel):
    """
    Component information model.

    Attributes:
        component_type: Component type (activity, service, receiver, provider)
        component_name: Full component class name
        is_exported: Whether the component is exported
        intent_filters: List of intent filter actions
        risk_level: Risk level assessment
    """

    component_type: str
    component_name: str
    is_exported: bool
    intent_filters: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW


class ApkBasicInfo(BaseModel):
    """
    APK basic information model.

    Attributes:
        package_name: Package name
        app_name: Application name
        version_name: Version name (e.g., "1.0.0")
        version_code: Version code (integer)
        min_sdk: Minimum SDK version
        target_sdk: Target SDK version
        file_size: APK file size in bytes
        md5: MD5 hash of APK file
        sha256: SHA256 hash of APK file
        signature: APK signature
        is_debuggable: Whether the APK is debuggable
        is_packed: Whether the APK is packed
        packer_name: Name of the packer if packed
    """

    package_name: str
    app_name: str
    version_name: str
    version_code: int
    file_size: int
    md5: str
    sha256: str
    min_sdk: Optional[int] = None
    target_sdk: Optional[int] = None
    signature: Optional[str] = None
    is_debuggable: bool = False
    is_packed: bool = False
    packer_name: Optional[str] = None


class StaticAnalysisResult(BaseModel):
    """
    Static analysis result model.

    Attributes:
        basic_info: APK basic information
        permissions: List of permissions
        components: List of components
        native_libraries: List of native library names
        suspicious_apis: List of suspicious API names
        analysis_time: Analysis timestamp
    """

    basic_info: ApkBasicInfo
    permissions: List[PermissionInfo] = Field(default_factory=list)
    components: List[ComponentInfo] = Field(default_factory=list)
    native_libraries: List[str] = Field(default_factory=list)
    suspicious_apis: List[str] = Field(default_factory=list)
    analysis_time: datetime = Field(default_factory=datetime.utcnow)


class NetworkRequest(BaseModel):
    """
    Network request model.

    Attributes:
        request_id: Unique request identifier
        url: Request URL
        domain: Domain name
        ip: IP address
        port: Port number
        method: HTTP method (GET, POST, etc.)
        is_https: Whether the request uses HTTPS
        request_time: Request timestamp
        response_code: HTTP response code
        content_type: Response content type
        is_whitelisted: Whether the domain is whitelisted
        whitelist_category: Whitelist category if whitelisted
        risk_level: Risk level assessment
        risk_reason: Reason for the risk assessment
    """

    request_id: str
    url: str
    domain: str
    ip: str
    port: int
    method: str
    is_https: bool
    request_time: datetime
    response_code: Optional[int] = None
    content_type: Optional[str] = None
    is_whitelisted: bool = False
    whitelist_category: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    risk_reason: Optional[str] = None


class SensitiveApiCall(BaseModel):
    """
    Sensitive API call model.

    Attributes:
        api_name: API method name
        api_class: Class name that the API belongs to
        call_count: Number of times the API was called
        first_call_time: First call timestamp
        last_call_time: Last call timestamp
        risk_level: Risk level assessment
        description: API description
    """

    api_name: str
    api_class: str
    call_count: int
    first_call_time: datetime
    last_call_time: datetime
    risk_level: RiskLevel = RiskLevel.LOW
    description: Optional[str] = None


class Screenshot(BaseModel):
    """
    Screenshot model.

    Attributes:
        screenshot_id: Unique screenshot identifier
        step_number: Operation step number
        operation_type: Operation type (click, input, etc.)
        operation_detail: Detailed operation description
        screenshot_path: Screenshot file path
        capture_time: Screenshot capture timestamp
        ai_description: AI-generated description of the screenshot
    """

    screenshot_id: str
    step_number: int
    operation_type: str
    operation_detail: str
    screenshot_path: str
    capture_time: datetime
    ai_description: Optional[str] = None


class DynamicAnalysisResult(BaseModel):
    """
    Dynamic analysis result model.

    Attributes:
        network_requests: List of network requests
        sensitive_api_calls: List of sensitive API calls
        screenshots: List of screenshots
        analysis_duration_seconds: Analysis duration in seconds
        analysis_time: Analysis timestamp
    """

    network_requests: List[NetworkRequest] = Field(default_factory=list)
    sensitive_api_calls: List[SensitiveApiCall] = Field(default_factory=list)
    screenshots: List[Screenshot] = Field(default_factory=list)
    analysis_duration_seconds: int
    analysis_time: datetime = Field(default_factory=datetime.utcnow)


class AnalysisResult(BaseModel):
    """
    Complete analysis result model.

    Attributes:
        task_id: Associated task ID
        static_analysis: Static analysis result
        dynamic_analysis: Dynamic analysis result
        overall_risk_level: Overall risk level assessment
        risk_points: List of identified risk points
        recommendations: List of security recommendations
        analysis_time: Analysis completion timestamp
    """

    task_id: str
    static_analysis: Optional[StaticAnalysisResult] = None
    dynamic_analysis: Optional[DynamicAnalysisResult] = None
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_points: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    analysis_time: datetime = Field(default_factory=datetime.utcnow)
