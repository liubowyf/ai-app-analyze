"""Tests for task orchestration state machine."""

from modules.task_orchestration.state_machine import (
    get_retry_delay_seconds,
    is_terminal_status,
    next_stage,
    next_status_after_stage,
)


def test_next_stage_is_deterministic():
    assert next_stage("pending") == "static"
    assert next_stage("queued") == "static"
    assert next_stage("static_analyzing") == "dynamic"
    assert next_stage("dynamic_analyzing") == "report"
    assert next_stage("completed") is None
    assert next_stage("failed") is None


def test_next_status_after_stage_mapping():
    assert next_status_after_stage("static") == "static_analyzing"
    assert next_status_after_stage("dynamic") == "dynamic_analyzing"
    assert next_status_after_stage("report") == "report_generating"


def test_terminal_status_detection():
    assert is_terminal_status("completed") is True
    assert is_terminal_status("failed") is True
    assert is_terminal_status("queued") is False


def test_retry_delay_uses_capped_backoff_sequence():
    delays = (5, 15, 45)
    assert get_retry_delay_seconds(retry_count=0, delays=delays) == 5
    assert get_retry_delay_seconds(retry_count=1, delays=delays) == 15
    assert get_retry_delay_seconds(retry_count=10, delays=delays) == 45
