"""Test static analyzer."""
import pytest
from types import SimpleNamespace


def test_static_analysis_entrypoint_exists():
    """Static analyzer should expose callable stage entrypoint."""
    from workers.static_analyzer import run_static_analysis

    assert callable(run_static_analysis)


def test_apk_analyzer_extract_package_name():
    """Test APK analyzer can extract package name."""
    from modules.apk_analyzer.analyzer import ApkAnalyzer

    # This is a placeholder test - real test needs actual APK
    analyzer = ApkAnalyzer()
    assert analyzer is not None


def test_apk_analyzer_falls_back_to_aapt_when_androguard_fails(monkeypatch, tmp_path):
    import modules.apk_analyzer.analyzer as analyzer_module

    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"fake")

    badging_output = "\n".join(
        [
            "package: name='com.demo.app' versionCode='12' versionName='1.2.3'",
            "sdkVersion:'21'",
            "targetSdkVersion:'28'",
            "application-label:'Demo App'",
            "uses-permission: name='android.permission.INTERNET'",
            "uses-permission: name='android.permission.ACCESS_FINE_LOCATION'",
            "launchable-activity: name='com.demo.MainActivity'",
            "native-code: 'arm64-v8a' 'armeabi-v7a'",
        ]
    )

    monkeypatch.setattr(
        analyzer_module,
        "AnalyzeAPK",
        lambda _: (_ for _ in ()).throw(ValueError("bad manifest")),
    )
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=badging_output, stderr=""))

    result = analyzer_module.ApkAnalyzer().analyze(
        apk_path=str(apk_path),
        file_size=4,
        md5="abc",
    )

    assert result.basic_info.package_name == "com.demo.app"
    assert result.basic_info.app_name == "Demo App"
    assert result.basic_info.version_code == 12
    assert result.basic_info.target_sdk == 28
    assert [perm.name for perm in result.permissions] == [
        "android.permission.INTERNET",
        "android.permission.ACCESS_FINE_LOCATION",
    ]
    assert result.components[0].component_name == "com.demo.MainActivity"
    assert result.native_libraries == ["arm64-v8a", "armeabi-v7a"]


def test_apk_analyzer_falls_back_to_aapt_from_bytes_when_androguard_fails(monkeypatch):
    import modules.apk_analyzer.analyzer as analyzer_module

    badging_output = "\n".join(
        [
            "package: name='com.demo.bytes' versionCode='7' versionName='7.0.0'",
            "sdkVersion:'23'",
            "targetSdkVersion:'30'",
            "application-label:'Bytes Demo'",
        ]
    )

    monkeypatch.setattr(
        analyzer_module,
        "AnalyzeAPK",
        lambda _: (_ for _ in ()).throw(ValueError("bad manifest")),
    )
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=badging_output, stderr=""))

    result = analyzer_module.ApkAnalyzer().analyze(
        apk_content=b"fake-apk-bytes",
        file_size=14,
        md5="def",
    )

    assert result.basic_info.package_name == "com.demo.bytes"
    assert result.basic_info.app_name == "Bytes Demo"
    assert result.basic_info.target_sdk == 30
