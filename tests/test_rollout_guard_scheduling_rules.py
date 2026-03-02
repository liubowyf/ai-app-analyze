"""Additional scheduling rule tests for rollout guard."""

from scripts.rollout_guard import decide_rollout_action


def test_scheduling_guard_holds_when_sample_size_below_minimum():
    snapshot = {
        "validation_mode": "scheduling",
        "can_enqueue": True,
        "rollback_ready": True,
        "stuck_tasks": 0,
        "total_tasks": 2,
        "success_rate": 1.0,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling", min_sample=3)

    assert action == "hold"
    assert reason == "insufficient_sample_size"


def test_scheduling_guard_rolls_back_immediately_when_stuck_exists_even_under_min_sample():
    snapshot = {
        "validation_mode": "scheduling",
        "can_enqueue": True,
        "rollback_ready": True,
        "stuck_tasks": 1,
        "total_tasks": 1,
        "success_rate": 1.0,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling", min_sample=3)

    assert action == "rollback_now"
    assert reason == "scheduling_stuck_tasks_detected"


def test_scheduling_guard_checks_success_rate_after_min_sample_reached():
    snapshot = {
        "validation_mode": "scheduling",
        "can_enqueue": True,
        "rollback_ready": True,
        "stuck_tasks": 0,
        "total_tasks": 5,
        "success_rate": 0.9,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling", min_sample=3)

    assert action == "rollback_now"
    assert reason == "scheduling_success_rate_low"


def test_scheduling_guard_default_min_sample_is_30():
    snapshot = {
        "validation_mode": "scheduling",
        "can_enqueue": True,
        "rollback_ready": True,
        "stuck_tasks": 0,
        "total_tasks": 29,
        "success_rate": 1.0,
    }

    action, reason = decide_rollout_action(snapshot, validation_mode="scheduling")

    assert action == "hold"
    assert reason == "insufficient_sample_size"
