"""Tests for exploration runtime policy."""

from modules.exploration_strategy.policy import ExplorationPolicy


def test_policy_from_env_parses_runtime_controls(monkeypatch):
    monkeypatch.setenv("APP_EXPLORATION_MAX_STEPS", "120")
    monkeypatch.setenv("APP_EXPLORATION_MAX_CLICKS_PER_SCREEN", "4")
    monkeypatch.setenv("APP_EXPLORATION_STAGNANT_THRESHOLD", "3")
    monkeypatch.setenv("APP_EXPLORATION_MAX_RECOVERY_ATTEMPTS", "7")
    monkeypatch.setenv("APP_EXPLORATION_WIDGET_BLACKLIST", "跳过,广告,关闭")
    monkeypatch.setenv("APP_EXPLORATION_WIDGET_WHITELIST", "首页,发现")
    monkeypatch.setenv("APP_EXPLORATION_SKIP_KEYWORDS", "登录,支付")
    monkeypatch.setenv("APP_EXPLORATION_ENABLE_CLEAR_DATA_RECOVERY", "true")
    monkeypatch.setenv("APP_EXPLORATION_ENABLE_REINSTALL_RECOVERY", "1")

    policy = ExplorationPolicy.from_env()

    assert policy.max_steps == 120
    assert policy.max_clicks_per_screen == 4
    assert policy.stagnant_threshold == 3
    assert policy.max_recovery_attempts == 7
    assert policy.widget_blacklist == ["跳过", "广告", "关闭"]
    assert policy.widget_whitelist == ["首页", "发现"]
    assert policy.skip_keywords == ["登录", "支付"]
    assert policy.enable_clear_data_recovery is True
    assert policy.enable_reinstall_recovery is True


def test_policy_from_env_uses_safe_defaults(monkeypatch):
    monkeypatch.delenv("APP_EXPLORATION_MAX_STEPS", raising=False)
    monkeypatch.delenv("APP_EXPLORATION_WIDGET_BLACKLIST", raising=False)

    policy = ExplorationPolicy.from_env()

    assert policy.max_steps >= 50
    assert isinstance(policy.widget_blacklist, list)
