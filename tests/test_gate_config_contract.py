"""Contract tests for gate runtime configuration defaults and overrides."""

from __future__ import annotations

from scripts.phase4_gate_check import CommandResult, run_phase4_gate_check
from scripts.gate_config import GateRuntimeConfig, load_gate_runtime_config


def test_gate_runtime_config_defaults(monkeypatch):
    for key in (
        "GATE_COLLECT_TIMEOUT_SECONDS",
        "GATE_PHASE5_RUNS",
        "GATE_WINDOW_MINUTES",
        "GATE_MIN_SAMPLE",
    ):
        monkeypatch.delenv(key, raising=False)

    config = load_gate_runtime_config()

    assert config == GateRuntimeConfig(
        collect_timeout_seconds=30,
        phase5_runs=3,
        window_minutes=30,
        guard_min_sample=30,
    )


def test_gate_runtime_config_env_overrides(monkeypatch):
    monkeypatch.setenv("GATE_COLLECT_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("GATE_PHASE5_RUNS", "5")
    monkeypatch.setenv("GATE_WINDOW_MINUTES", "40")
    monkeypatch.setenv("GATE_MIN_SAMPLE", "50")

    config = load_gate_runtime_config()

    assert config.collect_timeout_seconds == 45
    assert config.phase5_runs == 5
    assert config.window_minutes == 40
    assert config.guard_min_sample == 50


def test_gate_runtime_config_invalid_env_falls_back_to_defaults(monkeypatch):
    monkeypatch.setenv("GATE_COLLECT_TIMEOUT_SECONDS", "abc")
    monkeypatch.setenv("GATE_PHASE5_RUNS", "-1")
    monkeypatch.setenv("GATE_WINDOW_MINUTES", "0")
    monkeypatch.setenv("GATE_MIN_SAMPLE", "")

    config = load_gate_runtime_config()

    assert config.collect_timeout_seconds == 30
    assert config.phase5_runs == 3
    assert config.window_minutes == 30
    assert config.guard_min_sample == 30


def test_phase4_gate_check_uses_configured_min_sample(monkeypatch):
    monkeypatch.setenv("GATE_MIN_SAMPLE", "45")
    guard_commands = []

    def fake_runner(cmd: list[str]) -> CommandResult:
        joined = " ".join(cmd)
        if "verify_collect_stability.py" in joined:
            return CommandResult(returncode=0, stdout="[PASS] collect", stderr="")
        if "pytest --collect-only -q" in joined:
            return CommandResult(returncode=0, stdout="349 tests collected", stderr="")
        if "scheduling_window_snapshot.py" in joined:
            return CommandResult(returncode=0, stdout="snapshot_ok", stderr="")
        if "rollout_guard.py" in joined:
            guard_commands.append(joined)
            return CommandResult(returncode=0, stdout="action=continue\nreason=all_gates_passed\n", stderr="")
        if "rollback_smoke.py" in joined:
            return CommandResult(returncode=0, stdout="rollback_ready=True\n", stderr="")
        return CommandResult(returncode=1, stdout="", stderr=f"unexpected command: {joined}")

    code, report = run_phase4_gate_check(runner=fake_runner)

    assert code == 0
    assert report["final_action"] == "continue"
    assert any("--min-sample 45" in command for command in guard_commands)
