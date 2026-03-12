"""Tests for exploration runtime policy."""

from modules.exploration_strategy.policy import ExplorationPolicy


def test_policy_from_env_parses_runtime_controls(monkeypatch):
    monkeypatch.setenv("APP_EXPLORATION_MAX_STEPS", "120")
    monkeypatch.setenv("APP_EXPLORATION_TOTAL_ACTION_BUDGET", "25")
    monkeypatch.setenv("APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET", "25")
    monkeypatch.setenv("APP_EXPLORATION_MAX_CLICKS_PER_SCREEN", "4")
    monkeypatch.setenv("APP_EXPLORATION_STAGNANT_THRESHOLD", "3")
    monkeypatch.setenv("APP_EXPLORATION_MAX_RECOVERY_ATTEMPTS", "7")
    monkeypatch.setenv("APP_EXPLORATION_WIDGET_BLACKLIST", "跳过,广告,关闭")
    monkeypatch.setenv("APP_EXPLORATION_WIDGET_WHITELIST", "首页,发现")
    monkeypatch.setenv("APP_EXPLORATION_SKIP_KEYWORDS", "登录,支付")
    monkeypatch.setenv("APP_EXPLORATION_ENABLE_CLEAR_DATA_RECOVERY", "true")
    monkeypatch.setenv("APP_EXPLORATION_ENABLE_REINSTALL_RECOVERY", "1")
    monkeypatch.setenv("APP_EXPLORATION_TIME_BUDGET_SECONDS", "600")
    monkeypatch.setenv("APP_EXPLORATION_SCENARIO_ACTION_BUDGET", "30")
    monkeypatch.setenv("APP_EXPLORATION_RELAUNCH_CYCLES", "6")
    monkeypatch.setenv("APP_EXPLORATION_SKIP_PERMISSION_GRANT", "false")

    policy = ExplorationPolicy.from_env()

    assert policy.max_steps == 120
    assert policy.total_action_budget == 25
    assert policy.total_screenshot_budget == 25
    assert policy.max_clicks_per_screen == 4
    assert policy.stagnant_threshold == 3
    assert policy.max_recovery_attempts == 7
    assert policy.widget_blacklist == ["跳过", "广告", "关闭"]
    assert policy.widget_whitelist == ["首页", "发现"]
    assert policy.skip_keywords == ["登录", "支付"]
    assert policy.time_budget_seconds == 600
    assert policy.scenario_action_budget == 30
    assert policy.relaunch_cycles == 6
    assert policy.skip_permission_grant is False
    assert policy.enable_clear_data_recovery is True
    assert policy.enable_reinstall_recovery is True


def test_policy_from_env_uses_safe_defaults(monkeypatch):
    monkeypatch.delenv("APP_EXPLORATION_MAX_STEPS", raising=False)
    monkeypatch.delenv("APP_EXPLORATION_TOTAL_ACTION_BUDGET", raising=False)
    monkeypatch.delenv("APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET", raising=False)
    monkeypatch.delenv("APP_EXPLORATION_WIDGET_BLACKLIST", raising=False)

    policy = ExplorationPolicy.from_env()

    assert policy.max_steps == 25
    assert policy.total_action_budget == 25
    assert policy.total_screenshot_budget == 25
    assert isinstance(policy.widget_blacklist, list)
    assert policy.skip_permission_grant is False
