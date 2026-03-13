"""Test static analyzer."""
import io
import zipfile

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


def test_apk_analyzer_prefers_aapt_and_extracts_icon(monkeypatch, tmp_path):
    import modules.apk_analyzer.analyzer as analyzer_module

    apk_path = tmp_path / "icon-sample.apk"
    with zipfile.ZipFile(apk_path, "w") as apk_zip:
        apk_zip.writestr("res/mipmap-xxhdpi-v4/ic_launcher.png", b"\x89PNG\r\n\x1a\nICON")

    badging_output = "\n".join(
        [
            "package: name='com.demo.icon' versionCode='1' versionName='1.0.0'",
            "application-label:'Icon Demo'",
            "application-icon-240:'res/mipmap-xxhdpi-v4/ic_launcher.png'",
        ]
    )

    def fail_androguard(_):
        raise AssertionError("AnalyzeAPK should not be used in lightweight happy path")

    monkeypatch.setattr(analyzer_module, "AnalyzeAPK", fail_androguard)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=badging_output, stderr=""),
    )

    analyzer = analyzer_module.ApkAnalyzer()
    result = analyzer.analyze(apk_path=str(apk_path), file_size=apk_path.stat().st_size, md5="abc")

    assert result.basic_info.package_name == "com.demo.icon"
    assert result.basic_info.icon_resource_path == "res/mipmap-xxhdpi-v4/ic_launcher.png"
    assert result.basic_info.icon_content_type == "image/png"
    assert analyzer.icon_bytes == b"\x89PNG\r\n\x1a\nICON"


def test_apk_analyzer_accepts_aapt_nonzero_when_badging_has_package_data(monkeypatch, tmp_path):
    import modules.apk_analyzer.analyzer as analyzer_module

    apk_path = tmp_path / "nonzero-aapt.apk"
    with zipfile.ZipFile(apk_path, "w") as apk_zip:
        apk_zip.writestr("res/o-_.png", b"\x89PNG\r\n\x1a\nICON")

    badging_output = "\n".join(
        [
            "AndroidManifest.xml:80: error: ERROR getting 'android:icon' attribute: attribute is not a string value",
            "package: name='com.gov.mafjesse' versionCode='102' versionName='1.0.2'",
            "sdkVersion:'21'",
            "targetSdkVersion:'30'",
            "application-label:'征途国际'",
            "application-icon-640:'res/o-_.png'",
            "launchable-activity: name='com.example.sports.activity.SplashActivity'",
        ]
    )

    def fail_androguard(_):
        raise AssertionError("AnalyzeAPK should not be used when aapt badging already yielded package data")

    monkeypatch.setattr(analyzer_module, "AnalyzeAPK", fail_androguard)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=badging_output, stderr=""),
    )

    analyzer = analyzer_module.ApkAnalyzer()
    result = analyzer.analyze(apk_path=str(apk_path), file_size=apk_path.stat().st_size, md5="bb4806791a0707c2bf3eef9aeb573aa0")

    assert result.basic_info.package_name == "com.gov.mafjesse"
    assert result.basic_info.app_name == "征途国际"
    assert result.basic_info.version_name == "1.0.2"
    assert result.basic_info.target_sdk == 30
    assert result.basic_info.icon_resource_path == "res/o-_.png"
    assert analyzer.icon_bytes == b"\x89PNG\r\n\x1a\nICON"
