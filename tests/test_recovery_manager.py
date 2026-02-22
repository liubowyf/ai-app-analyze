"""Tests for exploration recovery manager."""

from modules.exploration_strategy.recovery_manager import RecoveryConfig, RecoveryManager


def test_recovery_action_escalates_from_back_to_force_stop():
    manager = RecoveryManager(RecoveryConfig(enable_clear_data=False, enable_reinstall=False))

    a1 = manager.next_action(stagnation_count=1, error_count=0)
    a2 = manager.next_action(stagnation_count=3, error_count=0)
    a3 = manager.next_action(stagnation_count=5, error_count=1)

    assert a1.kind == "back"
    assert a2.kind == "home_relaunch"
    assert a3.kind == "force_stop_relaunch"


def test_recovery_action_supports_clear_data_and_reinstall():
    manager = RecoveryManager(RecoveryConfig(enable_clear_data=True, enable_reinstall=True))

    clear_data = manager.next_action(stagnation_count=8, error_count=3)
    reinstall = manager.next_action(stagnation_count=12, error_count=5)

    assert clear_data.kind == "clear_data_relaunch"
    assert reinstall.kind == "reinstall_app"
