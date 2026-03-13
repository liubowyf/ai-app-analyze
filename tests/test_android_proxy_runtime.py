"""Runtime tests for Android proxy baseline preflight."""

import logging

import pytest

import modules.traffic_monitor.android_proxy_runtime as runtime


def _clear_proxy_baseline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "ANDROID_HTTP_PROXY_BASELINE",
        "EMULATOR_HTTP_PROXY_BASELINE",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(key, raising=False)


def test_preflight_android_proxy_before_install_restores_baseline_proxy(monkeypatch, caplog):
    state = {"proxy": "127.0.0.1:18080"}
    commands = []
    _clear_proxy_baseline_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", "http://10.16.150.4:3128")

    class FakeRunner:
        def execute_adb_remote(self, host, port, cmd):
            commands.append((host, port, cmd))
            if "settings get global http_proxy" in cmd:
                return state["proxy"]
            if cmd.startswith("shell settings put global http_proxy "):
                state["proxy"] = cmd.rsplit(" ", 1)[-1]
                return "ok"
            return "ok"

    monkeypatch.setattr("modules.android_runner.AndroidRunner", FakeRunner)

    with caplog.at_level(logging.INFO):
        result = runtime.preflight_android_proxy_before_install("10.16.148.66", 5555)

    assert result["before_proxy"] == "127.0.0.1:18080"
    assert result["after_proxy"] == "10.16.150.4:3128"
    assert result["action"] == "restore_baseline_proxy"
    assert any("settings put global http_proxy 10.16.150.4:3128" in cmd for _, _, cmd in commands)
    assert "Android proxy preflight before install on 10.16.148.66:5555 -> 127.0.0.1:18080" in caplog.text


def test_preflight_android_proxy_before_install_raises_when_residual_proxy_persists(monkeypatch):
    commands = []
    state = {"proxy": "127.0.0.1:18080"}
    _clear_proxy_baseline_env(monkeypatch)

    class FakeRunner:
        def execute_adb_remote(self, host, port, cmd):
            commands.append((host, port, cmd))
            if "settings get global http_proxy" in cmd:
                return state["proxy"]
            return "ok"

    monkeypatch.setattr("modules.android_runner.AndroidRunner", FakeRunner)

    with pytest.raises(RuntimeError, match="Android proxy preflight failed"):
        runtime.preflight_android_proxy_before_install("10.16.148.66", 5555)

    assert any("settings put global http_proxy :0" in cmd for _, _, cmd in commands)
