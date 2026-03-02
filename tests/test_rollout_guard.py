"""Tests for rollout guard trigger decision script."""

from scripts.rollout_guard import decide_rollout_action


def test_decide_rollout_action_returns_continue_when_all_gates_pass():
    snapshot = {
        "backend": "dramatiq",
        "can_enqueue": True,
        "success_rate": 0.97,
        "tasks": [
            {"task_id": "ok-1", "runs": 3, "network": 10, "domains": 3, "img_count": 8},
            {"task_id": "ok-2", "runs": 2, "network": 8, "domains": 2, "img_count": 5},
        ],
    }

    action, reason = decide_rollout_action(snapshot)

    assert action == "continue"
    assert reason == "all_gates_passed"


def test_decide_rollout_action_rolls_back_when_can_enqueue_false():
    snapshot = {"backend": "dramatiq", "can_enqueue": False, "success_rate": 1.0, "tasks": []}

    action, reason = decide_rollout_action(snapshot)

    assert action == "rollback_now"
    assert reason == "backend_not_ready"


def test_decide_rollout_action_rolls_back_when_zero_evidence_task_exists():
    snapshot = {
        "backend": "dramatiq",
        "can_enqueue": True,
        "success_rate": 1.0,
        "tasks": [
            {"task_id": "bad-1", "runs": 0, "network": 10, "domains": 3, "img_count": 4},
            {"task_id": "ok-1", "runs": 3, "network": 10, "domains": 3, "img_count": 4},
        ],
    }

    action, reason = decide_rollout_action(snapshot)

    assert action == "rollback_now"
    assert reason == "zero_evidence_task_detected"


def test_decide_rollout_action_rolls_back_when_failure_rate_above_5_percent():
    snapshot = {"backend": "dramatiq", "can_enqueue": True, "success_rate": 0.94, "tasks": []}

    action, reason = decide_rollout_action(snapshot)

    assert action == "rollback_now"
    assert reason == "failure_rate_above_5_percent"


def test_decide_rollout_action_scheduling_continue_when_gates_pass():
    snapshot = {
        "validation_mode": "scheduling",
        "backend": "dramatiq",
        "can_enqueue": True,
        "rollback_ready": True,
        "total_tasks": 40,
        "success_rate": 0.97,
        "stuck_tasks": 0,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling")

    assert action == "continue"
    assert reason == "all_gates_passed"


def test_decide_rollout_action_scheduling_rolls_back_when_stuck_tasks_present():
    snapshot = {
        "validation_mode": "scheduling",
        "backend": "dramatiq",
        "can_enqueue": True,
        "rollback_ready": True,
        "success_rate": 1.0,
        "stuck_tasks": 1,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling")

    assert action == "rollback_now"
    assert reason == "scheduling_stuck_tasks_detected"
