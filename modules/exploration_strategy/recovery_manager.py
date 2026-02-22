"""Recovery strategy manager for stalled exploration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecoveryConfig:
    """Controls optional heavy recovery actions."""

    enable_clear_data: bool = False
    enable_reinstall: bool = False
    max_attempts: int = 6


@dataclass
class RecoveryAction:
    """Selected recovery action."""

    kind: str
    reason: str


class RecoveryManager:
    """Escalate recovery actions based on stagnation/error pressure."""

    def __init__(self, config: RecoveryConfig):
        self.config = config

    def next_action(self, stagnation_count: int, error_count: int) -> RecoveryAction:
        pressure = max(0, stagnation_count) + max(0, error_count)

        if pressure <= 2:
            return RecoveryAction("back", "minor stall detected")
        if pressure <= 4:
            return RecoveryAction("home_relaunch", "stall persists, relaunch from home")
        if pressure <= 7:
            return RecoveryAction("force_stop_relaunch", "deep stall, force-stop app")

        if self.config.enable_clear_data and pressure <= 11:
            return RecoveryAction("clear_data_relaunch", "state corruption suspected, clear data")

        if self.config.enable_reinstall:
            return RecoveryAction("reinstall_app", "persistent failures, reinstall app")

        return RecoveryAction("force_stop_relaunch", "max safe recovery")
