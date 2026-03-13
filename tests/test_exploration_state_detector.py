"""Tests for UI state detector."""

from modules.exploration_strategy.state_detector import StateDetector


class _FakeRunner:
    def __init__(self):
        self.activity = "com.demo/.MainActivity"
        self.window = "com.demo/com.demo.MainActivity"
        self.ui_xml = '<hierarchy><node text="首页"/></hierarchy>'
        self.screenshot = b"png-bytes"

    def get_current_activity(self, host, port):
        return self.activity

    def get_current_window(self, host, port):
        return self.window

    def dump_ui_hierarchy(self, host, port):
        return self.ui_xml

    def take_screenshot_remote(self, host, port):
        return self.screenshot


def test_snapshot_contains_state_fingerprints():
    detector = StateDetector(android_runner=_FakeRunner(), stagnant_threshold=2)

    state = detector.snapshot("127.0.0.1", 5555)

    assert state.activity == "com.demo/.MainActivity"
    assert state.window == "com.demo/com.demo.MainActivity"
    assert len(state.ui_hash) == 32
    assert len(state.screenshot_hash) == 32


def test_stagnation_detected_when_same_state_repeats():
    runner = _FakeRunner()
    detector = StateDetector(android_runner=runner, stagnant_threshold=2)

    s1 = detector.snapshot("127.0.0.1", 5555)
    detector.record(s1)
    assert detector.is_stagnant(s1) is False

    s2 = detector.snapshot("127.0.0.1", 5555)
    detector.record(s2)
    assert detector.is_stagnant(s2) is True


def test_stagnation_resets_after_state_change():
    runner = _FakeRunner()
    detector = StateDetector(android_runner=runner, stagnant_threshold=2)

    s1 = detector.snapshot("127.0.0.1", 5555)
    detector.record(s1)
    detector.record(s1)
    assert detector.is_stagnant(s1) is True

    runner.activity = "com.demo/.DetailActivity"
    runner.window = "com.demo/com.demo.DetailActivity"
    runner.ui_xml = '<hierarchy><node text="详情"/></hierarchy>'

    s2 = detector.snapshot("127.0.0.1", 5555)
    detector.record(s2)
    assert detector.is_stagnant(s2) is False
