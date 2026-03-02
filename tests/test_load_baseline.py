"""Tests for load baseline recommendation helpers."""

from modules.task_orchestration.load_baseline import (
    build_worker_commands,
    count_configured_emulators,
    recommend_worker_baseline,
)


def test_count_configured_emulators_deduplicates_and_validates():
    count = count_configured_emulators(
        [
            "10.0.0.1:5555",
            "10.0.0.1:5555",
            "10.0.0.2:5556",
            "bad-value",
            "10.0.0.3:abc",
        ]
    )
    assert count == 2


def test_recommend_worker_baseline_caps_dynamic_by_emulators():
    baseline = recommend_worker_baseline(emulator_count=3, cpu_count=16)
    assert baseline["dynamic_worker_concurrency"] == 3
    assert baseline["api_workers"] <= 4
    assert baseline["static_worker_concurrency"] >= 2
    assert baseline["report_worker_concurrency"] >= 2


def test_build_worker_commands_contains_dramatiq_worker_command():
    baseline = recommend_worker_baseline(emulator_count=2, cpu_count=8)
    commands = build_worker_commands(baseline)
    assert len(commands) == 2
    assert commands[0].startswith("uvicorn api.main:app")
    assert commands[1].startswith("dramatiq workers.task_actor")
