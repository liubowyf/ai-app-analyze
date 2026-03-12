"""APK static analyzer using androguard."""
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from typing import Dict, List, Any, Optional

from androguard.misc import AnalyzeAPK

from models.analysis_result import (
    ApkBasicInfo,
    PermissionInfo,
    ComponentInfo,
    StaticAnalysisResult,
)
from .risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

_PACKAGE_RE = re.compile(r"package:\s+name='([^']+)'.*versionCode='([^']*)'.*versionName='([^']*)'")
_SDK_RE = re.compile(r"sdkVersion:'([^']+)'")
_TARGET_SDK_RE = re.compile(r"targetSdkVersion:'([^']+)'")
_APP_LABEL_RE = re.compile(r"application-label:'([^']*)'")
_PERMISSION_RE = re.compile(r"uses-permission:\s+name='([^']+)'")
_LAUNCHABLE_ACTIVITY_RE = re.compile(r"launchable-activity:\s+name='([^']+)'")
_NATIVE_CODE_RE = re.compile(r"'([^']+)'")


@lru_cache(maxsize=100)
def cached_analyze_apk(apk_path: str, apk_md5: str):
    """
    Cache APK parsing results to avoid re-parsing same APK.

    Args:
        apk_path: Path to APK file
        apk_md5: MD5 hash of APK (used as cache key)

    Returns:
        Tuple of (APK object, DalvikVMs, Analysis)
    """
    return AnalyzeAPK(apk_path)


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
        if apk_path:
            return self._analyze_path_with_fallback(
                apk_path=apk_path,
                file_size=file_size,
                md5=md5,
                sha256=sha256,
            )

        if apk_content:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
                tmp.write(apk_content)
                tmp_path = tmp.name
            try:
                return self._analyze_path_with_fallback(
                    apk_path=tmp_path,
                    file_size=file_size,
                    md5=md5,
                    sha256=sha256,
                )
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        raise ValueError("Either apk_path or apk_content must be provided")

    def _analyze_path_with_fallback(
        self,
        apk_path: str,
        file_size: int,
        md5: str,
        sha256: str,
    ) -> StaticAnalysisResult:
        try:
            self.apk, self.analysis, _ = AnalyzeAPK(apk_path)
            return StaticAnalysisResult(
                basic_info=self.extract_basic_info(file_size, md5, sha256),
                permissions=self.extract_permissions(),
                components=self.extract_components(),
            )
        except Exception as exc:
            logger.warning("AnalyzeAPK failed for %s, falling back to aapt: %s", apk_path, exc)
            return self._analyze_with_aapt(
                apk_path=apk_path,
                file_size=file_size,
                md5=md5,
                sha256=sha256,
            )

    def _analyze_with_aapt(
        self,
        apk_path: str,
        file_size: int,
        md5: str,
        sha256: str,
    ) -> StaticAnalysisResult:
        aapt_path = shutil.which("aapt")
        if not aapt_path:
            raise ValueError(f"Failed to load APK from {apk_path}")

        proc = subprocess.run(
            [aapt_path, "dump", "badging", apk_path],
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        if proc.returncode != 0 or "package: name='" not in output:
            raise ValueError(f"Failed to load APK from {apk_path}")

        package_match = _PACKAGE_RE.search(output)
        if not package_match:
            raise ValueError(f"Failed to load APK from {apk_path}")

        sdk_match = _SDK_RE.search(output)
        target_sdk_match = _TARGET_SDK_RE.search(output)
        app_label_match = _APP_LABEL_RE.search(output)
        permissions = list(dict.fromkeys(_PERMISSION_RE.findall(output)))
        launchable_activity = _LAUNCHABLE_ACTIVITY_RE.search(output)
        native_code_line = next(
            (line for line in output.splitlines() if line.startswith("native-code:")),
            "",
        )

        basic_info = ApkBasicInfo(
            package_name=package_match.group(1),
            app_name=app_label_match.group(1) if app_label_match else "",
            version_name=package_match.group(3),
            version_code=int(package_match.group(2) or 0),
            min_sdk=int(sdk_match.group(1)) if sdk_match and sdk_match.group(1).isdigit() else None,
            target_sdk=int(target_sdk_match.group(1)) if target_sdk_match and target_sdk_match.group(1).isdigit() else None,
            file_size=file_size,
            md5=md5,
            sha256=sha256,
            signature="",
            is_debuggable=False,
            is_packed=False,
            packer_name=None,
        )

        permission_items = []
        for permission in permissions:
            if permission in DANGEROUS_PERMISSIONS:
                risk_level, risk_reason = DANGEROUS_PERMISSIONS[permission]
                protection_level = "dangerous" if risk_level in ("high", "critical") else "normal"
            else:
                risk_level = "low"
                risk_reason = None
                protection_level = "unknown"

            permission_items.append(
                PermissionInfo(
                    name=permission,
                    protection_level=protection_level,
                    description=risk_reason,
                    risk_level=risk_level,
                    risk_reason=risk_reason,
                )
            )

        components = []
        if launchable_activity:
            components.append(
                ComponentInfo(
                    component_type="activity",
                    component_name=launchable_activity.group(1),
                    is_exported=True,
                    intent_filters=["android.intent.action.MAIN"],
                    risk_level="medium",
                )
            )

        native_libraries = _NATIVE_CODE_RE.findall(native_code_line)
        self.apk = None
        self.analysis = None

        return StaticAnalysisResult(
            basic_info=basic_info,
            permissions=permission_items,
            components=components,
            native_libraries=native_libraries,
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
