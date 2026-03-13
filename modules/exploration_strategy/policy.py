"""Runtime policy for app exploration behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _parse_int(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "y"}


def _parse_list(name: str, default: List[str] | None = None) -> List[str]:
    raw = os.getenv(name, "")
    items = [item.strip() for item in raw.split(",") if item.strip()]
    if items:
        return items
    return list(default or [])


@dataclass
class ExplorationPolicy:
    """Runtime policy knobs for resilient exploration."""

    max_steps: int = 25
    total_action_budget: int = 25
    total_screenshot_budget: int = 25
    max_clicks_per_screen: int = 3
    stagnant_threshold: int = 2
    max_recovery_attempts: int = 6
    widget_blacklist: List[str] = field(default_factory=list)
    widget_whitelist: List[str] = field(default_factory=list)
    skip_keywords: List[str] = field(default_factory=lambda: [
        "登录", "注册", "验证码", "密码", "支付", "实名认证", "人脸", "指纹", "银行卡",
    ])
    enable_form_interaction: bool = True
    max_form_interactions_per_screen: int = 2
    form_submit_keywords: List[str] = field(default_factory=lambda: [
        "登录", "注册", "下一步", "提交", "确认", "确定", "继续", "完成", "发送", "获取验证码",
    ])
    ai_step_timeout_seconds: int = 20
    time_budget_seconds: int = 540
    scenario_action_budget: int = 24
    relaunch_cycles: int = 4
    dialog_repeat_limit: int = 3
    dialog_repeat_limit_with_form: int = 1
    skip_permission_grant: bool = False
    enable_clear_data_recovery: bool = False
    enable_reinstall_recovery: bool = False

    @classmethod
    def from_env(cls) -> "ExplorationPolicy":
        """Build exploration policy from environment variables."""
        return cls(
            max_steps=_parse_int("APP_EXPLORATION_MAX_STEPS", 25, 5, 500),
            total_action_budget=_parse_int("APP_EXPLORATION_TOTAL_ACTION_BUDGET", 25, 5, 500),
            total_screenshot_budget=_parse_int("APP_EXPLORATION_TOTAL_SCREENSHOT_BUDGET", 25, 1, 500),
            max_clicks_per_screen=_parse_int("APP_EXPLORATION_MAX_CLICKS_PER_SCREEN", 3, 1, 20),
            stagnant_threshold=_parse_int("APP_EXPLORATION_STAGNANT_THRESHOLD", 2, 1, 20),
            max_recovery_attempts=_parse_int("APP_EXPLORATION_MAX_RECOVERY_ATTEMPTS", 6, 1, 20),
            widget_blacklist=_parse_list("APP_EXPLORATION_WIDGET_BLACKLIST"),
            widget_whitelist=_parse_list("APP_EXPLORATION_WIDGET_WHITELIST"),
            skip_keywords=_parse_list("APP_EXPLORATION_SKIP_KEYWORDS", [
                "登录", "注册", "验证码", "密码", "支付", "实名认证", "人脸", "指纹", "银行卡",
            ]),
            enable_form_interaction=_parse_bool("APP_EXPLORATION_ENABLE_FORM_INTERACTION", True),
            max_form_interactions_per_screen=_parse_int(
                "APP_EXPLORATION_MAX_FORM_INTERACTIONS_PER_SCREEN",
                2,
                1,
                10,
            ),
            form_submit_keywords=_parse_list("APP_EXPLORATION_FORM_SUBMIT_KEYWORDS", [
                "登录", "注册", "下一步", "提交", "确认", "确定", "继续", "完成", "发送", "获取验证码",
            ]),
            ai_step_timeout_seconds=_parse_int(
                "APP_EXPLORATION_AI_STEP_TIMEOUT_SECONDS",
                20,
                5,
                180,
            ),
            time_budget_seconds=_parse_int(
                "APP_EXPLORATION_TIME_BUDGET_SECONDS",
                540,
                60,
                3600,
            ),
            scenario_action_budget=_parse_int(
                "APP_EXPLORATION_SCENARIO_ACTION_BUDGET",
                24,
                4,
                200,
            ),
            relaunch_cycles=_parse_int(
                "APP_EXPLORATION_RELAUNCH_CYCLES",
                4,
                1,
                20,
            ),
            dialog_repeat_limit=_parse_int(
                "APP_EXPLORATION_DIALOG_REPEAT_LIMIT",
                3,
                1,
                20,
            ),
            dialog_repeat_limit_with_form=_parse_int(
                "APP_EXPLORATION_DIALOG_REPEAT_LIMIT_WITH_FORM",
                1,
                1,
                10,
            ),
            skip_permission_grant=_parse_bool("APP_EXPLORATION_SKIP_PERMISSION_GRANT", False),
            enable_clear_data_recovery=_parse_bool("APP_EXPLORATION_ENABLE_CLEAR_DATA_RECOVERY", False),
            enable_reinstall_recovery=_parse_bool("APP_EXPLORATION_ENABLE_REINSTALL_RECOVERY", False),
        )
