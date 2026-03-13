from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import subprocess


class _FakeQuery:
    def __init__(self, task):
        self.task = task

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.task


class _FakeSession:
    def __init__(self, task):
        self.task = task
        self.closed = False
        self.rollback_called = False

    def query(self, model):
        return _FakeQuery(self.task)

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


def test_redroid_remote_backend_runs_and_persists(monkeypatch, tmp_path):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(
        id="task-redroid-1",
        apk_storage_path="apks/task-redroid-1/demo.apk",
        static_analysis_result={"basic_info": {"package_name": "com.demo.app"}},
        dynamic_analysis_result=None,
        error_message=None,
        status="pending",
    )
    fake_session = _FakeSession(task)

    helper_calls: list[tuple[str, object]] = []

    def fake_commit(db, context=""):
        helper_calls.append(("commit", context))

    def fake_persist(**kwargs):
        helper_calls.append(("persist", kwargs["task_id"]))

    def fake_stage_details(**kwargs):
        helper_calls.append(("stage_details", kwargs["network_analysis"].get("capture_mode")))
        return {"capture_mode": kwargs["network_analysis"].get("capture_mode")}

    fake_helpers = SimpleNamespace(
        _get_static_package_name=lambda result: result["basic_info"]["package_name"],
        _detect_package_name=lambda apk_path: "com.demo.fallback",
        _preflight_emulator_proxy_before_install=lambda **kwargs: helper_calls.append(("preflight", kwargs["host"])),
        _build_dynamic_result=lambda **kwargs: {
            "capture_mode": "redroid_zeek",
            "network_analysis": kwargs["traffic_monitor"].analyze_traffic(),
        },
        _build_dynamic_quality_gate=lambda **kwargs: {"degraded": False, "reason": None},
        _persist_dynamic_normalized_tables=fake_persist,
        _build_dynamic_stage_run_details=fake_stage_details,
        _commit_with_retry=fake_commit,
        _mark_task_failed=lambda task_id, error: helper_calls.append(("mark_failed", task_id)),
        MAX_DB_SCREENSHOTS=25,
        MAX_DB_REQUESTS=1000,
    )

    class FakeADBClient:
        def __init__(self, serial):
            self.serial = serial

        def connect(self):
            helper_calls.append(("adb_connect", self.serial))
            return True

    class FakeSSHClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_file(self, remote_path, local_path, timeout=30):
            if remote_path.endswith("tcpdump.log"):
                Path(local_path).write_text(
                    "12:00:00.000001 IP 172.17.0.2.54321 > 10.16.150.4.3128: Flags [P.], seq 1:10, ack 1, win 512, length 9\n"
                    "CONNECT example.com:443 HTTP/1.1\n"
                    "Host: example.com:443\n",
                    encoding="utf-8",
                )
                return local_path
            Path(local_path).write_text(
                "#separator \\x09\n#path conn\n#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state\tlocal_orig\tlocal_resp\tmissed_bytes\thistory\torig_pkts\torig_ip_bytes\tresp_pkts\tresp_ip_bytes\ttunnel_parents\n"
                "1700000000.0\tuid1\t172.17.0.2\t54321\t1.1.1.1\t443\ttcp\thttp\t0.4\t123\t456\tSF\t-\t-\t0\tShADadf\t10\t800\t11\t900\t-\n",
                encoding="utf-8",
            )
            return local_path

    class FakeCollector:
        def __init__(self, ssh_client, container_name):
            helper_calls.append(("collector_init", container_name))

        def start_capture(self, task_id):
            helper_calls.append(("capture_start", task_id))
            return {
                "pcap_path": "/tmp/demo.pcap",
                "text_path": "/tmp/demo.log",
                "zeek_dir": "/tmp/zeek-demo",
                "pid": 123,
            }

        def stop_capture(self, capture):
            helper_calls.append(("capture_stop", capture["pid"]))

        def run_zeek(self, capture):
            helper_calls.append(("run_zeek", capture["pcap_path"]))
            return {**capture, "pcap_exists": False, "pcap_size": 0}

    class FakeDeviceController:
        def __init__(self, adb_client):
            self.adb_client = adb_client

        def dump_ui_xml(self, local_dir, file_name="window_dump.xml"):
            path = Path(local_dir) / file_name
            path.write_text("<hierarchy/>", encoding="utf-8")
            helper_calls.append(("dump_ui", str(path)))
            return str(path)

    class FakeExplorer:
        def __init__(self, **kwargs):
            helper_calls.append(("explorer_init", True))

        def run_full_exploration(self, emulator_config, apk_info):
            helper_calls.append(("explore", emulator_config["host"], apk_info["package_name"], apk_info.get("activity_name")))
            return SimpleNamespace(
                total_steps=4,
                screenshots=[{"stage": "launch", "description": "ok", "storage_path": "screenshots/demo.png"}],
                activities_visited=["com.demo/.Main"],
                success=True,
                error_message=None,
                phases_completed=["setup", "nav"],
                history=[],
            )

    class FakeAdapter:
        def get_requests(self):
            return [{"host": "example.com", "ip": "1.1.1.1", "hit_count": 2, "source_type": "conn"}]

        def get_candidate_requests(self):
            return []

        def analyze_traffic(self):
            return {
                "capture_mode": "redroid_zeek",
                "source_breakdown": {"conn": 2},
            }

        def get_requests_as_dict(self):
            return self.get_requests()

        def get_candidate_requests_as_dict(self):
            return []

        def get_aggregated_requests(self):
            return self.get_requests()

        def get_candidate_aggregated_requests(self):
            return []

        def get_domain_stats(self):
            return [{"domain": "example.com", "ip": "1.1.1.1", "hit_count": 2, "source_types": ["conn"]}]

    monkeypatch.setattr(backend_module, "_dynamic_helpers", lambda: fake_helpers)
    monkeypatch.setattr(backend_module, "_resolve_activity_name", lambda task, apk_path: "com.demo.app.MainActivity")
    monkeypatch.setattr(backend_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(backend_module, "storage_client", SimpleNamespace(download_file=lambda path: b"apk-bytes"))
    monkeypatch.setattr(
        backend_module,
        "RedroidLeaseManager",
        lambda *args, **kwargs: SimpleNamespace(
            acquire=lambda task_id: {
                "name": "redroid-1",
                "adb_serial": "61.152.73.88:16555",
                "container_name": "redroid-1",
            },
            release=lambda task_id, slot_name=None: helper_calls.append(("release_slot", slot_name)),
        ),
    )
    monkeypatch.setattr(
        backend_module,
        "settings",
        SimpleNamespace(
            REDROID_SSH_HOST="61.152.73.88",
            REDROID_SSH_PORT=22,
            REDROID_SSH_USER="tester",
            REDROID_SSH_KEY_PATH="",
            REDROID_SSH_PASSWORD="",
            REDROID_LEASE_TTL_SECONDS=1800,
            REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS=60,
            REDROID_LEASE_POLL_INTERVAL_SECONDS=1.0,
            redroid_slots=[{"name": "redroid-1", "adb_serial": "61.152.73.88:16555", "container_name": "redroid-1"}],
            AI_BASE_URL="http://ai.local/v1",
            AI_MODEL_NAME="demo-model",
            AI_API_KEY="EMPTY",
        ),
    )
    monkeypatch.setattr(backend_module, "RedroidADBClient", FakeADBClient)
    monkeypatch.setattr(backend_module, "RedroidSSHClient", FakeSSHClient)
    monkeypatch.setattr(backend_module, "RedroidTrafficCollector", FakeCollector)
    monkeypatch.setattr(backend_module, "RedroidDeviceController", FakeDeviceController)
    monkeypatch.setattr(backend_module, "ScreenshotManager", lambda task_id: SimpleNamespace(task_id=task_id))
    monkeypatch.setattr(backend_module, "AndroidRunner", lambda: SimpleNamespace())
    monkeypatch.setattr(backend_module, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(backend_module, "ExplorationPolicy", SimpleNamespace(from_env=lambda: SimpleNamespace()))
    monkeypatch.setattr(backend_module, "AppExplorer", FakeExplorer)
    monkeypatch.setattr(
        backend_module,
        "parse_zeek_outputs",
        lambda **kwargs: {"observations": [{"domain": "example.com", "ip": "1.1.1.1", "source_type": "connect"}]},
    )
    monkeypatch.setattr(
        backend_module,
        "assemble_redroid_observation_adapter",
        lambda parsed: (
            FakeAdapter(),
            {"master_domains": [{"domain": "example.com", "ip": "1.1.1.1", "score": 2, "confidence": "observed"}]},
        ),
    )
    monkeypatch.setattr(backend_module, "start_stage_run", lambda *args, **kwargs: helper_calls.append(("start_stage", kwargs["task_id"])))
    monkeypatch.setattr(backend_module, "finish_stage_run", lambda *args, **kwargs: helper_calls.append(("finish_stage", kwargs["task_id"])))
    monkeypatch.setattr(backend_module, "update_stage_context", lambda *args, **kwargs: helper_calls.append(("update_stage", kwargs["emulator"])))

    result = backend_module.RedroidRemoteDynamicBackend().run("task-redroid-1")

    assert result["backend"] == "redroid_remote"
    assert result["capture_mode"] == "redroid_zeek"
    assert result["network_requests"] == 1
    assert task.dynamic_analysis_result["redroid_artifacts"]["pcap_path"] == "/tmp/demo.pcap"
    assert task.dynamic_analysis_result["redroid_artifacts"]["pcap_exists"] is False
    assert task.dynamic_analysis_result["redroid_artifacts"]["tcpdump_log_path"] is not None
    assert ("capture_start", "task-redroid-1") in helper_calls
    assert ("run_zeek", "/tmp/demo.pcap") in helper_calls
    assert ("finish_stage", "task-redroid-1") in helper_calls
    assert ("explore", "61.152.73.88", "com.demo.app", "com.demo.app.MainActivity") in helper_calls
    assert ("release_slot", "redroid-1") in helper_calls
    assert fake_session.closed is True


def test_redroid_remote_backend_requires_ssh_user(monkeypatch):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(
        id="task-redroid-2",
        apk_storage_path="apks/task-redroid-2/demo.apk",
        static_analysis_result={},
        dynamic_analysis_result=None,
        error_message=None,
        status="pending",
    )
    fake_session = _FakeSession(task)
    failures: list[tuple[str, str]] = []

    fake_helpers = SimpleNamespace(
        _mark_task_failed=lambda task_id, error: failures.append((task_id, error)),
    )

    monkeypatch.setattr(backend_module, "_dynamic_helpers", lambda: fake_helpers)
    monkeypatch.setattr(backend_module, "_resolve_activity_name", lambda task, apk_path: "com.demo.app.MainActivity")
    monkeypatch.setattr(backend_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(
        backend_module,
        "settings",
        SimpleNamespace(
            REDROID_SSH_HOST="61.152.73.88",
            REDROID_SSH_PORT=22,
            REDROID_SSH_USER="",
            REDROID_SSH_KEY_PATH="",
            REDROID_SSH_PASSWORD="",
            REDROID_LEASE_TTL_SECONDS=1800,
            REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS=60,
            REDROID_LEASE_POLL_INTERVAL_SECONDS=1.0,
            redroid_slots=[{"name": "redroid-1", "adb_serial": "61.152.73.88:16555", "container_name": "redroid-1"}],
            AI_BASE_URL="http://ai.local/v1",
            AI_MODEL_NAME="demo-model",
            AI_API_KEY="EMPTY",
        ),
    )
    monkeypatch.setattr(backend_module, "start_stage_run", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="REDROID_SSH_USER"):
        backend_module.RedroidRemoteDynamicBackend().run("task-redroid-2")

    assert failures
    assert failures[0][0] == "task-redroid-2"
    assert fake_session.closed is True


def test_redroid_remote_backend_marks_failure_when_exploration_fails(monkeypatch):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(
        id="task-redroid-fail",
        apk_storage_path="apks/task-redroid-fail/demo.apk",
        static_analysis_result={"basic_info": {"package_name": "com.demo.app"}},
        dynamic_analysis_result=None,
        error_message=None,
        status="pending",
    )
    fake_session = _FakeSession(task)
    failures: list[tuple[str, str]] = []

    fake_helpers = SimpleNamespace(
        _get_static_package_name=lambda result: result["basic_info"]["package_name"],
        _detect_package_name=lambda apk_path: "com.demo.fallback",
        _preflight_emulator_proxy_before_install=lambda **kwargs: None,
        _build_dynamic_result=lambda **kwargs: {"capture_mode": "redroid_zeek", "network_analysis": {}},
        _build_dynamic_quality_gate=lambda **kwargs: {"degraded": False, "reason": None},
        _persist_dynamic_normalized_tables=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not persist success payload")),
        _build_dynamic_stage_run_details=lambda **kwargs: {},
        _commit_with_retry=lambda db, context="": None,
        _mark_task_failed=lambda task_id, error: failures.append((task_id, error)),
        MAX_DB_SCREENSHOTS=25,
        MAX_DB_REQUESTS=1000,
    )

    class FakeADBClient:
        def __init__(self, serial):
            self.serial = serial

        def connect(self):
            return True

    class FakeSSHClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fetch_file(self, remote_path, local_path, timeout=30):
            Path(local_path).write_text("", encoding="utf-8")
            return local_path

    class FakeCollector:
        def __init__(self, ssh_client, container_name):
            return None

        def start_capture(self, task_id):
            return {"pcap_path": "/tmp/demo.pcap", "text_path": "/tmp/demo.log", "zeek_dir": "/tmp/zeek-demo", "pid": 123}

        def stop_capture(self, capture):
            return None

        def run_zeek(self, capture):
            return {**capture, "pcap_exists": False, "pcap_size": 0}

    class FakeDeviceController:
        def __init__(self, adb_client):
            self.adb_client = adb_client

        def dump_ui_xml(self, local_dir, file_name="window_dump.xml"):
            path = Path(local_dir) / file_name
            path.write_text("<hierarchy/>", encoding="utf-8")
            return str(path)

    class FailingExplorer:
        def __init__(self, **kwargs):
            pass

        def run_full_exploration(self, emulator_config, apk_info):
            return SimpleNamespace(
                total_steps=1,
                screenshots=[{"stage": "install", "description": "APK安装完成", "storage_path": None, "image_base64": None}],
                activities_visited=["com.android.launcher3/.Launcher"],
                success=False,
                error_message="Target app launch failed: com.gov.mafjesse not foreground",
                phases_completed=["setup"],
                history=[],
            )

    monkeypatch.setattr(backend_module, "_dynamic_helpers", lambda: fake_helpers)
    monkeypatch.setattr(backend_module, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(backend_module, "storage_client", SimpleNamespace(download_file=lambda path: b"apk-bytes"))
    monkeypatch.setattr(
        backend_module,
        "RedroidLeaseManager",
        lambda *args, **kwargs: SimpleNamespace(
            acquire=lambda task_id: {
                "name": "redroid-1",
                "adb_serial": "61.152.73.88:16555",
                "container_name": "redroid-1",
            },
            release=lambda task_id, slot_name=None: None,
        ),
    )
    monkeypatch.setattr(
        backend_module,
        "settings",
        SimpleNamespace(
            REDROID_SSH_HOST="61.152.73.88",
            REDROID_SSH_PORT=22,
            REDROID_SSH_USER="tester",
            REDROID_SSH_KEY_PATH="",
            REDROID_SSH_PASSWORD="pw",
            REDROID_LEASE_TTL_SECONDS=1800,
            REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS=60,
            REDROID_LEASE_POLL_INTERVAL_SECONDS=1.0,
            redroid_slots=[{"name": "redroid-1", "adb_serial": "61.152.73.88:16555", "container_name": "redroid-1"}],
            AI_BASE_URL="http://ai.local/v1",
            AI_MODEL_NAME="demo-model",
            AI_API_KEY="EMPTY",
        ),
    )
    monkeypatch.setattr(backend_module, "RedroidADBClient", FakeADBClient)
    monkeypatch.setattr(backend_module, "RedroidSSHClient", FakeSSHClient)
    monkeypatch.setattr(backend_module, "RedroidTrafficCollector", FakeCollector)
    monkeypatch.setattr(backend_module, "RedroidDeviceController", FakeDeviceController)
    monkeypatch.setattr(backend_module, "ScreenshotManager", lambda task_id: SimpleNamespace(task_id=task_id))
    monkeypatch.setattr(backend_module, "AndroidRunner", lambda: SimpleNamespace())
    monkeypatch.setattr(backend_module, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(backend_module, "ExplorationPolicy", SimpleNamespace(from_env=lambda: SimpleNamespace()))
    monkeypatch.setattr(backend_module, "AppExplorer", FailingExplorer)
    monkeypatch.setattr(backend_module, "parse_zeek_outputs", lambda **kwargs: {"observations": []})
    monkeypatch.setattr(backend_module, "assemble_redroid_observation_adapter", lambda parsed: (SimpleNamespace(get_requests=lambda: [], get_candidate_requests=lambda: []), {"master_domains": []}))
    monkeypatch.setattr(backend_module, "start_stage_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_module, "finish_stage_run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not finish dynamic as success")))
    monkeypatch.setattr(backend_module, "update_stage_context", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="Target app launch failed"):
        backend_module.RedroidRemoteDynamicBackend().run("task-redroid-fail")

    assert failures == [("task-redroid-fail", "Target app launch failed: com.gov.mafjesse not foreground")]
    assert fake_session.closed is True


def test_resolve_activity_name_falls_back_to_manifest_xmltree(monkeypatch):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(static_analysis_result={"components": []})
    outputs = [
        "package: name='com.gov.mafjesse' versionCode='1' versionName='1.0'",
        "\n".join(
            [
                '      E: activity (line=292)',
                '        A: android:name(0x01010003)="com.example.sports.activity.SplashActivity" (Raw: "com.example.sports.activity.SplashActivity")',
                "        E: intent-filter (line=296)",
                "          E: action (line=297)",
                '            A: android:name(0x01010003)="android.intent.action.MAIN" (Raw: "android.intent.action.MAIN")',
                "          E: category (line=299)",
                '            A: android:name(0x01010003)="android.intent.category.LAUNCHER" (Raw: "android.intent.category.LAUNCHER")',
            ]
        ),
    ]

    def fake_check_output(cmd, text=True, stderr=None, timeout=30):
        return outputs.pop(0)

    monkeypatch.setattr(backend_module.subprocess, "check_output", fake_check_output)

    activity_name = backend_module._resolve_activity_name(task, "/tmp/demo.apk")

    assert activity_name == "com.example.sports.activity.SplashActivity"


def test_resolve_activity_name_still_uses_manifest_when_badging_fails(monkeypatch):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(static_analysis_result={"components": []})

    def fake_check_output(cmd, text=True, stderr=None, timeout=30):
        if cmd[2] == "badging":
            raise subprocess.CalledProcessError(1, cmd, output="badging failed")
        return "\n".join(
            [
                "      E: activity (line=292)",
                '        A: android:name(0x01010003)="com.example.sports.activity.SplashActivity" (Raw: "com.example.sports.activity.SplashActivity")',
                "        E: intent-filter (line=296)",
                '            A: android:name(0x01010003)="android.intent.action.MAIN" (Raw: "android.intent.action.MAIN")',
                '            A: android:name(0x01010003)="android.intent.category.LAUNCHER" (Raw: "android.intent.category.LAUNCHER")',
            ]
        )

    monkeypatch.setattr(backend_module.subprocess, "check_output", fake_check_output)

    activity_name = backend_module._resolve_activity_name(task, "/tmp/demo.apk")

    assert activity_name == "com.example.sports.activity.SplashActivity"


def test_resolve_activity_name_prefers_manifest_over_static_component_order(monkeypatch):
    from modules.analysis_backends import redroid_remote as backend_module

    task = SimpleNamespace(
        static_analysis_result={
            "components": [
                {"component_type": "activity", "component_name": "com.vivo.push.sdk.LinkProxyClientActivity", "intent_filters": []},
                {"component_type": "activity", "component_name": "com.example.sports.activity.SplashActivity", "intent_filters": ["android.intent.action.MAIN"]},
            ]
        }
    )
    outputs = [
        "package: name='com.gov.mafjesse' versionCode='1' versionName='1.0'",
        "\n".join(
            [
                '        A: android:name(0x01010003)="com.example.sports.activity.SplashActivity" (Raw: "com.example.sports.activity.SplashActivity")',
                '            A: android:name(0x01010003)="android.intent.action.MAIN" (Raw: "android.intent.action.MAIN")',
                '            A: android:name(0x01010003)="android.intent.category.LAUNCHER" (Raw: "android.intent.category.LAUNCHER")',
            ]
        ),
    ]
    monkeypatch.setattr(backend_module.subprocess, "check_output", lambda *args, **kwargs: outputs.pop(0))

    activity_name = backend_module._resolve_activity_name(task, "/tmp/demo.apk")

    assert activity_name == "com.example.sports.activity.SplashActivity"
