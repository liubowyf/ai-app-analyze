"""APK static analyzer using androguard."""
import hashlib
from typing import Dict, List, Any, Optional
import logging

from androguard.misc import AnalyzeAPK

from models.analysis_result import (
    ApkBasicInfo,
    PermissionInfo,
    ComponentInfo,
    StaticAnalysisResult,
)

logger = logging.getLogger(__name__)


# Dangerous permissions mapping
DANGEROUS_PERMISSIONS = {
    "android.permission.READ_CONTACTS": ("high", "读取联系人"),
    "android.permission.WRITE_CONTACTS": ("high", "写入联系人"),
    "android.permission.READ_SMS": ("high", "读取短信"),
    "android.permission.SEND_SMS": ("high", "发送短信"),
    "android.permission.RECEIVE_SMS": ("high", "接收短信"),
    "android.permission.READ_CALL_LOG": ("high", "读取通话记录"),
    "android.permission.WRITE_CALL_LOG": ("high", "写入通话记录"),
    "android.permission.PROCESS_OUTGOING_CALLS": ("high", "监听拨出电话"),
    "android.permission.READ_PHONE_STATE": ("medium", "读取设备状态"),
    "android.permission.ACCESS_FINE_LOCATION": ("high", "精确定位"),
    "android.permission.ACCESS_COARSE_LOCATION": ("medium", "粗略定位"),
    "android.permission.CAMERA": ("medium", "使用相机"),
    "android.permission.RECORD_AUDIO": ("high", "录音"),
    "android.permission.READ_EXTERNAL_STORAGE": ("medium", "读取存储"),
    "android.permission.WRITE_EXTERNAL_STORAGE": ("medium", "写入存储"),
}


class ApkAnalyzer:
    """APK static analyzer class."""

    def __init__(self):
        """Initialize APK analyzer."""
        self.apk: Any = None  # androguard APK object
        self.analysis: Any = None

    def load_apk(self, apk_path: str) -> bool:
        """
        Load APK file for analysis.

        Args:
            apk_path: Path to APK file

        Returns:
            True if loaded successfully
        """
        try:
            self.apk, self.analysis, dx = AnalyzeAPK(apk_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load APK: {e}")
            return False

    def load_apk_from_bytes(self, apk_content: bytes) -> bool:
        """
        Load APK from bytes.

        Args:
            apk_content: APK file content as bytes

        Returns:
            True if loaded successfully
        """
        try:
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
                tmp.write(apk_content)
                tmp_path = tmp.name
            try:
                self.apk, self.analysis, dx = AnalyzeAPK(tmp_path)
            finally:
                os.unlink(tmp_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load APK from bytes: {e}")
            return False

    def extract_basic_info(self, file_size: int = 0, md5: str = "", sha256: str = "") -> ApkBasicInfo:
        """
        Extract basic information from APK.

        Args:
            file_size: File size in bytes
            md5: MD5 hash
            sha256: SHA256 hash

        Returns:
            ApkBasicInfo object
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        return ApkBasicInfo(
            package_name=self.apk.get_package() or "",
            app_name=self.apk.get_app_name() or "",
            version_name=self.apk.get_androidversion_name() or "",
            version_code=self.apk.get_androidversion_code() or 0,
            min_sdk=self.apk.get_min_sdk_version() or 0,
            target_sdk=self.apk.get_target_sdk_version() or 0,
            file_size=file_size,
            md5=md5,
            sha256=sha256,
            signature=self._get_signature_info(),
            is_debuggable=self._is_debuggable(),
            is_packed=False,
            packer_name=None,
        )

    def extract_permissions(self) -> List[PermissionInfo]:
        """
        Extract permissions from APK.

        Returns:
            List of PermissionInfo objects
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        permissions = []
        for perm in self.apk.get_permissions():
            perm_name = perm.split(".")[-1] if "." in perm else perm
            protection_level = "unknown"

            # Determine protection level
            if perm in DANGEROUS_PERMISSIONS:
                risk_level, risk_reason = DANGEROUS_PERMISSIONS[perm]
                protection_level = "dangerous" if risk_level in ("high", "critical") else "normal"
            else:
                risk_level = "low"
                risk_reason = None

            permissions.append(PermissionInfo(
                name=perm,
                protection_level=protection_level,
                description=risk_reason,
                risk_level=risk_level,
                risk_reason=risk_reason,
            ))

        return permissions

    def _get_signature_info(self) -> str:
        """Get APK signature information."""
        if not self.apk:
            return ""
        try:
            certs = self.apk.get_certificates()
            if certs:
                # Get the first certificate's subject
                cert = certs[0]
                return str(cert)
        except Exception as e:
            logger.warning(f"Failed to get signature: {e}")
        return ""

    def _is_debuggable(self) -> bool:
        """Check if APK is debuggable."""
        if not self.apk:
            return False
        try:
            # Check AndroidManifest for android:debuggable attribute
            manifest = self.apk.get_android_manifest_xml()
            if manifest is not None:
                application = manifest.find("application")
                if application is not None:
                    debuggable = application.get(
                        "{http://schemas.android.com/apk/res/android}debuggable", "false"
                    )
                    return debuggable == "true" or debuggable is True
        except Exception as e:
            logger.warning(f"Failed to check debuggable: {e}")
        return False

    def analyze(self, apk_path: str = None, apk_content: bytes = None,
                file_size: int = 0, md5: str = "", sha256: str = "") -> StaticAnalysisResult:
        """
        Perform complete static analysis.

        Args:
            apk_path: Path to APK file
            apk_content: APK content as bytes
            file_size: File size in bytes
            md5: MD5 hash
            sha256: SHA256 hash

        Returns:
            StaticAnalysisResult object
        """
        # Load APK
        if apk_path:
            if not self.load_apk(apk_path):
                raise ValueError(f"Failed to load APK from {apk_path}")
        elif apk_content:
            if not self.load_apk_from_bytes(apk_content):
                raise ValueError("Failed to load APK from bytes")
        else:
            raise ValueError("Either apk_path or apk_content must be provided")

        # Extract all information
        basic_info = self.extract_basic_info(file_size, md5, sha256)
        permissions = self.extract_permissions()
        components = self.extract_components()

        return StaticAnalysisResult(
            basic_info=basic_info,
            permissions=permissions,
            components=components,
        )

    def extract_components(self) -> List[ComponentInfo]:
        """
        Extract components from APK.

        Returns:
            List of ComponentInfo objects
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        components = []

        # Activities
        for activity in self.apk.get_activities():
            components.append(ComponentInfo(
                component_type="activity",
                component_name=activity,
                is_exported=self._is_component_exported(activity, "activity"),
                intent_filters=self._get_intent_filters(activity, "activity"),
                risk_level="medium" if self._is_component_exported(activity, "activity") else "low",
            ))

        # Services
        for service in self.apk.get_services():
            components.append(ComponentInfo(
                component_type="service",
                component_name=service,
                is_exported=self._is_component_exported(service, "service"),
                intent_filters=self._get_intent_filters(service, "service"),
                risk_level="medium" if self._is_component_exported(service, "service") else "low",
            ))

        # Receivers
        for receiver in self.apk.get_receivers():
            components.append(ComponentInfo(
                component_type="receiver",
                component_name=receiver,
                is_exported=self._is_component_exported(receiver, "receiver"),
                intent_filters=self._get_intent_filters(receiver, "receiver"),
                risk_level="medium" if self._is_component_exported(receiver, "receiver") else "low",
            ))

        # Providers
        for provider in self.apk.get_providers():
            components.append(ComponentInfo(
                component_type="provider",
                component_name=provider,
                is_exported=self._is_component_exported(provider, "provider"),
                intent_filters=[],
                risk_level="medium" if self._is_component_exported(provider, "provider") else "low",
            ))

        return components

    def _is_component_exported(self, component_name: str, component_type: str) -> bool:
        """Check if a component is exported."""
        try:
            if component_type == "activity":
                return self.apk.get_android_manifest().xpath(
                    f'//activity[@android:name="{component_name}"]/@android:exported',
                    namespaces={"android": "http://schemas.android.com/apk/res/android"}
                )[0] == "true"
            # Similar for other types...
        except Exception:
            pass
        return False

    def _get_intent_filters(self, component_name: str, component_type: str) -> List[str]:
        """Get intent filters for a component."""
        return []  # Placeholder - implementation can be extended
