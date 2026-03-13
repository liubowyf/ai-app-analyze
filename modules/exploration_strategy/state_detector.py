"""Page state detection utilities for robust exploration."""

from __future__ import annotations

import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


@dataclass(frozen=True)
class UIState:
    """Snapshot of current UI state."""

    activity: str
    window: str
    ui_hash: str
    screenshot_hash: str
    ts: float

    @property
    def signature(self) -> str:
        return f"{self.activity}|{self.window}|{self.ui_hash}|{self.screenshot_hash}"


class StateDetector:
    """Detect stagnant UI state based on combined fingerprints."""

    def __init__(self, android_runner, stagnant_threshold: int = 2, history_size: int = 20):
        self.android_runner = android_runner
        self.stagnant_threshold = max(1, stagnant_threshold)
        self.history: Deque[str] = deque(maxlen=max(5, history_size))

    @staticmethod
    def _canonicalize_xml(ui_xml: str) -> str:
        if not ui_xml:
            return ""
        text = re.sub(r"\s+", " ", ui_xml).strip()
        # normalize changing indexes and bounds to reduce noise
        text = re.sub(r"index=\"\d+\"", 'index="0"', text)
        return text

    @staticmethod
    def _md5(data: bytes | str) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        return hashlib.md5(data).hexdigest()

    def snapshot(
        self,
        host: str,
        port: int,
        screenshot_data: Optional[bytes] = None,
        ui_xml: Optional[str] = None,
    ) -> UIState:
        """Collect state from activity/window/ui hierarchy/screenshot."""
        activity = self.android_runner.get_current_activity(host, port) or ""
        window_getter = getattr(self.android_runner, "get_current_window", None)
        if callable(window_getter):
            window = window_getter(host, port) or ""
        else:
            window = ""

        if ui_xml is None:
            dumper = getattr(self.android_runner, "dump_ui_hierarchy", None)
            if callable(dumper):
                result = dumper(host, port)
                ui_xml = result if isinstance(result, str) else ""
            else:
                ui_xml = ""

        if screenshot_data is None:
            screenshot_data = self.android_runner.take_screenshot_remote(host, port) or b""

        canonical_xml = self._canonicalize_xml(ui_xml)
        return UIState(
            activity=activity,
            window=window,
            ui_hash=self._md5(canonical_xml),
            screenshot_hash=self._md5(screenshot_data),
            ts=time.time(),
        )

    def record(self, state: UIState) -> None:
        """Record state signature for stagnation detection."""
        self.history.append(state.signature)

    def is_stagnant(self, state: UIState) -> bool:
        """Check whether latest consecutive states are identical."""
        if len(self.history) < self.stagnant_threshold:
            return False

        count = 0
        for signature in reversed(self.history):
            if signature != state.signature:
                break
            count += 1
            if count >= self.stagnant_threshold:
                return True
        return False
