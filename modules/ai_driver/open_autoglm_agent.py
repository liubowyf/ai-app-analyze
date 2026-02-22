"""Open-AutoGLM style prompt and action parsing helpers."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from typing import Any, Dict, Tuple


def build_system_prompt_zh() -> str:
    """Build Open-AutoGLM compatible Chinese system prompt."""
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    now = datetime.now()
    formatted_date = f"{now.strftime('%Y年%m月%d日')} {weekday_names[now.weekday()]}"
    return (
        f"今天的日期是: {formatted_date}\n"
        "你是一个智能体分析专家，可以根据操作历史和当前状态图执行一系列操作来完成任务。\n"
        "你必须严格输出以下格式：\n"
        "<think>{think}</think>\n"
        "<answer>{action}</answer>\n"
        "其中 action 只能是以下之一：\n"
        '- do(action="Launch", app="xxx")\n'
        '- do(action="Tap", element=[x,y])\n'
        '- do(action="Type", text="xxx")\n'
        '- do(action="Swipe", start=[x1,y1], end=[x2,y2])\n'
        '- do(action="Long Press", element=[x,y])\n'
        '- do(action="Double Tap", element=[x,y])\n'
        '- do(action="Back")\n'
        '- do(action="Home")\n'
        '- do(action="Wait", duration="x seconds")\n'
        '- do(action="Take_over", message="xxx")\n'
        '- finish(message="xxx")\n'
        "约束：\n"
        "1. 坐标使用 0-999 相对坐标。\n"
        "2. 优先操作目标 app，避免无意义等待。\n"
        "3. 页面无响应时可 Wait，但不要连续超过三次。\n"
        "4. 如果需要登录/验证码/人机校验，使用 Take_over。\n"
        "5. 不要输出任何与动作无关的解释文本。\n"
    )


def build_screen_info(current_app: str, goal: str, history: list[dict[str, Any]]) -> str:
    """Build Open-AutoGLM style user text payload."""
    compact_history = []
    for item in history[-8:]:
        compact_history.append(
            {
                "step": item.get("step"),
                "op": item.get("operation") or item.get("action"),
                "desc": item.get("description"),
            }
        )

    payload = {
        "task": goal,
        "screen_info": {"current_app": current_app},
        "recent_history": compact_history,
        "instruction": "请给出下一步最合适的单个动作",
    }
    return json.dumps(payload, ensure_ascii=False)


def split_thinking_and_action(content: str) -> Tuple[str, str]:
    """
    Parse model output into thinking and action using Open-AutoGLM markers.

    Priority:
    1) finish(message=
    2) do(action=
    3) <answer>...</answer>
    4) raw content fallback
    """
    if not content:
        return "", ""
    if "<answer>" in content:
        head, tail = content.split("<answer>", 1)
        action = tail.replace("</answer>", "").strip()
        thinking = head.replace("<think>", "").replace("</think>", "").strip()
        return thinking, action
    if "finish(message=" in content:
        head, tail = content.split("finish(message=", 1)
        return head.strip(), "finish(message=" + tail
    if "do(action=" in content:
        head, tail = content.split("do(action=", 1)
        return head.strip(), "do(action=" + tail
    return "", content.strip()


def parse_action(action_text: str) -> Dict[str, Any]:
    """Parse Open-AutoGLM do()/finish() action text into a dictionary."""
    text = (action_text or "").replace("</answer>", "").strip()
    if not text:
        raise ValueError("empty action")

    if text.startswith("finish"):
        message = ""
        m = re.search(r'finish\(message\s*=\s*"?(.*?)"?\)\s*$', text, re.DOTALL)
        if m:
            message = m.group(1)
        return {"_metadata": "finish", "message": message}

    if text.startswith('do(action="Type"') or text.startswith('do(action="Type_Name"'):
        m = re.search(r'text\s*=\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        return {
            "_metadata": "do",
            "action": "Type",
            "text": m.group(1) if m else "",
        }

    if text.startswith("do"):
        escaped = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        tree = ast.parse(escaped, mode="eval")
        if not isinstance(tree.body, ast.Call):
            raise ValueError("expected call")
        call = tree.body
        action: Dict[str, Any] = {"_metadata": "do"}
        for keyword in call.keywords:
            if not keyword.arg:
                continue
            action[keyword.arg] = ast.literal_eval(keyword.value)
        return action

    raise ValueError(f"unsupported action format: {text[:80]}")
