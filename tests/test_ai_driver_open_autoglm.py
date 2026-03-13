"""Tests for Open-AutoGLM style decision flow in AIDriver."""

from io import BytesIO
from types import SimpleNamespace

from modules.ai_driver.driver import AIDriver, OperationType
from modules.ai_driver.open_autoglm_agent import parse_action, split_thinking_and_action


def _png_bytes(width: int = 1000, height: int = 2000) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_split_thinking_and_action_prefers_do_marker():
    content = "先分析页面\ndo(action=\"Tap\", element=[500, 500])"
    thinking, action = split_thinking_and_action(content)
    assert "先分析页面" in thinking
    assert action.startswith("do(action=")


def test_parse_action_handles_do_and_finish():
    do_action = parse_action('do(action="Back")')
    assert do_action["_metadata"] == "do"
    assert do_action["action"] == "Back"

    finish_action = parse_action('finish(message="完成")')
    assert finish_action["_metadata"] == "finish"
    assert finish_action["message"] == "完成"


def test_analyze_and_decide_parses_open_autoglm_tap(monkeypatch):
    response_text = (
        "<think>页面中心按钮可点击</think>\n"
        '<answer>do(action="Tap", element=[500,500])</answer>'
    )

    fake_create = lambda **kwargs: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))]
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.analyze_and_decide(_png_bytes(), analysis_history=[], goal="探索")

    assert op.type == OperationType.TAP
    # relative [500,500] should map close to screen center
    assert 450 <= op.params["x"] <= 550
    assert 950 <= op.params["y"] <= 1050


def test_analyze_and_decide_parses_open_autoglm_swipe(monkeypatch):
    response_text = 'do(action="Swipe", start=[500,800], end=[500,200])'
    fake_create = lambda **kwargs: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))]
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.analyze_and_decide(_png_bytes(), analysis_history=[], goal="探索")

    assert op.type == OperationType.SWIPE
    assert all(k in op.params for k in ("start_x", "start_y", "end_x", "end_y"))


def test_analyze_and_decide_maps_takeover_to_wait(monkeypatch):
    response_text = 'do(action="Take_over", message="需要登录验证码")'
    fake_create = lambda **kwargs: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))]
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    driver = AIDriver(base_url="http://x/v1", model_name="m", api_key="k")
    monkeypatch.setattr(driver, "_get_client", lambda: fake_client)

    op = driver.analyze_and_decide(_png_bytes(), analysis_history=[], goal="探索")

    assert op.type == OperationType.WAIT
    assert "Take_over" in op.description
