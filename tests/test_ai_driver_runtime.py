"""Runtime behavior tests for AI driver."""
import sys
from types import SimpleNamespace

import pytest

import modules.ai_driver.driver as driver_module
from modules.ai_driver.driver import AIDriver, OperationType


class _FakeChatCompletions:
    """Capture create call arguments and return a fake response."""

    def __init__(self, content: str):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


def test_ai_driver_uses_settings_defaults(monkeypatch):
    """AIDriver should read base/model/key from settings when omitted."""
    fake_settings = SimpleNamespace(
        AI_BASE_URL="http://ai-gateway.local:9001/v1",
        AI_MODEL_NAME="autoglm-phone-test",
        AI_API_KEY="TEST_KEY",
    )
    monkeypatch.setattr(driver_module, "settings", fake_settings)

    driver = AIDriver()

    assert driver.base_url == fake_settings.AI_BASE_URL
    assert driver.model_name == fake_settings.AI_MODEL_NAME
    assert driver.api_key == fake_settings.AI_API_KEY


def test_analyze_screenshot_sends_base64_image_payload(monkeypatch):
    """Vision payload must be base64 data URL instead of hex string."""
    fake_create = _FakeChatCompletions("screen ok")
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=fake_create)
    )

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    raw = b"\x01\x02\x03\x04"
    result = driver.analyze_screenshot(raw, prompt="describe")

    assert result == "screen ok"
    image_url = fake_create.last_kwargs["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert "01020304" not in image_url  # not hex


@pytest.mark.parametrize("ai_type,expected", [("tap", OperationType.TAP), ("Click", OperationType.TAP)])
def test_decide_operation_parses_case_insensitive_operation_type(monkeypatch, ai_type, expected):
    """AI operation type mapping should tolerate lowercase/synonyms."""
    content = (
        "```json\n"
        '{'
        f'"type":"{ai_type}",'
        '"params":{"x":123,"y":456},'
        '"description":"tap target"'
        "}\n"
        "```"
    )
    fake_create = _FakeChatCompletions(content)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_create))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.decide_operation("screen", analysis_history=[])

    assert op.type == expected
    assert op.params["x"] == 123
    assert op.params["y"] == 456


def test_decide_operation_parses_tool_call_style_response(monkeypatch):
    """Non-JSON do(action=..., element=[x,y]) response should be executable."""
    content = (
        "I'll tap the agree button.\n"
        'do(action="Tap", element=[499, 651])'
    )
    fake_create = _FakeChatCompletions(content)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_create))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.decide_operation("screen", analysis_history=[])

    assert op.type == OperationType.TAP
    assert op.params["x"] == 499
    assert op.params["y"] == 651


def test_decide_operation_parses_simple_tap_with_coordinates(monkeypatch):
    """Simple `Tap: (x, y)` text should still produce a tap operation."""
    content = "Tap: (499, 526)"
    fake_create = _FakeChatCompletions(content)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_create))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.decide_operation("screen", analysis_history=[])

    assert op.type == OperationType.TAP
    assert op.params["x"] == 499
    assert op.params["y"] == 526


def test_decide_operation_parses_launch_and_wait_params(monkeypatch):
    """Tool-call text should parse Launch app and Wait duration fields."""
    content = (
        'do(action="Launch", app="微信")\n'
        'do(action="Wait", duration=3)'
    )
    fake_create = _FakeChatCompletions(content)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_create))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.decide_operation("screen", analysis_history=[])

    assert op.type == OperationType.LAUNCH
    assert op.params["app"] == "微信"


def test_get_client_passes_timeout_to_openai(monkeypatch):
    """OpenAI client should receive configured timeout to avoid hanging requests."""
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k", request_timeout=12.5)
    driver._get_client()

    assert captured["timeout"] == 12.5
