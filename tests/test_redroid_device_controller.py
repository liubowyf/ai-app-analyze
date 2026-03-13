from pathlib import Path

from modules.redroid_remote.adb_client import RedroidADBClient
from modules.redroid_remote.device_controller import RedroidDeviceController


class FakeADBClient:
    def __init__(self):
        self.calls = []

    def connect(self):
        self.calls.append(("connect",))
        return True

    def install_apk(self, apk_path, timeout=600):
        self.calls.append(("install_apk", apk_path, timeout))
        return "Success"

    def start_activity(self, package_name, activity_name, wait=True):
        self.calls.append(("start_activity", package_name, activity_name, wait))
        return "Starting: Intent"

    def shell(self, command, timeout=30):
        self.calls.append(("shell", command, timeout))
        return "OK"

    def pull(self, remote_path, local_path, timeout=30):
        self.calls.append(("pull", remote_path, local_path, timeout))
        Path(local_path).write_text("artifact")
        return str(local_path)


def test_adb_connect_command_uses_serial(monkeypatch):
    calls = []

    class FakeCompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = "connected to 61.152.73.88:16555\n"
            self.stderr = ""

    def fake_run(cmd, capture_output, text, timeout, check):
        calls.append(cmd)
        return FakeCompletedProcess()

    monkeypatch.setattr("modules.redroid_remote.adb_client.subprocess.run", fake_run)

    client = RedroidADBClient(serial="61.152.73.88:16555")
    assert client.connect() is True
    assert calls[0] == ["adb", "connect", "61.152.73.88:16555"]


def test_device_controller_installs_and_launches_app(tmp_path):
    adb = FakeADBClient()
    controller = RedroidDeviceController(adb)

    result = controller.install_and_launch(
        apk_path="/tmp/app.apk",
        package_name="com.demo.app",
        activity_name="com.demo.app.MainActivity",
    )

    assert result["install_result"] == "Success"
    assert result["launch_result"] == "Starting: Intent"
    assert adb.calls[:3] == [
        ("connect",),
        ("install_apk", "/tmp/app.apk", 600),
        ("start_activity", "com.demo.app", "com.demo.app.MainActivity", True),
    ]


def test_device_controller_captures_screenshot_and_pulls_to_local(tmp_path):
    adb = FakeADBClient()
    controller = RedroidDeviceController(adb)
    local_dir = tmp_path / "artifacts"

    result_path = controller.capture_screenshot(str(local_dir), file_name="screen-1.png")

    assert Path(result_path).exists()
    assert adb.calls[0] == ("shell", "screencap -p /sdcard/screen-1.png", 30)
    assert adb.calls[1] == ("pull", "/sdcard/screen-1.png", str(local_dir / "screen-1.png"), 30)


def test_device_controller_dumps_ui_xml_and_pulls_to_local(tmp_path):
    adb = FakeADBClient()
    controller = RedroidDeviceController(adb)
    local_dir = tmp_path / "artifacts"

    result_path = controller.dump_ui_xml(str(local_dir), file_name="window_dump.xml")

    assert Path(result_path).exists()
    assert adb.calls[0] == ("shell", "uiautomator dump /sdcard/window_dump.xml", 30)
    assert adb.calls[1] == ("pull", "/sdcard/window_dump.xml", str(local_dir / "window_dump.xml"), 30)
