"""AI Driver module using Open-AutoGLM style agent decision flow."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from core.config import settings
from modules.ai_driver.open_autoglm_agent import (
    build_screen_info,
    build_system_prompt_zh,
    parse_action,
    split_thinking_and_action,
)

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """AI operation types."""

    LAUNCH = "Launch"
    TAP = "Tap"
    TYPE = "Type"
    SWIPE = "Swipe"
    BACK = "Back"
    HOME = "Home"
    LONG_PRESS = "LongPress"
    DOUBLE_TAP = "DoubleTap"
    WAIT = "Wait"


@dataclass
class Operation:
    """AI operation to execute on Android device."""

    type: OperationType
    params: Dict[str, Any]
    description: str


class AIDriver:
    """AI driver for Android automation using OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ):
        self.base_url = base_url or settings.AI_BASE_URL
        self.model_name = model_name or settings.AI_MODEL_NAME
        self.api_key = api_key or settings.AI_API_KEY

        if request_timeout is None:
            try:
                request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
            except ValueError:
                request_timeout = 30.0
        self.request_timeout = max(3.0, min(float(request_timeout), 180.0))

        self.max_tokens = int(getattr(settings, "AI_MAX_TOKENS", 3000))
        self.temperature = float(getattr(settings, "AI_TEMPERATURE", 0.1))
        self.top_p = float(os.getenv("AI_TOP_P", "0.85"))
        self.frequency_penalty = float(os.getenv("AI_FREQUENCY_PENALTY", "0.2"))
        self.client: Optional[Any] = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self.client is None:
            try:
                from openai import OpenAI

                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout=self.request_timeout,
                )
            except ImportError:
                logger.error("openai package not installed")
                raise
        return self.client

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        """Extract first balanced JSON object from arbitrary text."""
        if not text:
            return None

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        candidate = fenced.group(1).strip() if fenced else text.strip()
        start = candidate.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return candidate[start : i + 1]
        return None

    @staticmethod
    def _normalize_operation_type(raw_type: str) -> OperationType:
        """Normalize operation type text into supported enum value."""
        value = (raw_type or "").strip().lower().replace(" ", "_")
        mapping = {
            "tap": OperationType.TAP,
            "click": OperationType.TAP,
            "doubletap": OperationType.DOUBLE_TAP,
            "double_tap": OperationType.DOUBLE_TAP,
            "double": OperationType.DOUBLE_TAP,
            "longpress": OperationType.LONG_PRESS,
            "long_press": OperationType.LONG_PRESS,
            "swipe": OperationType.SWIPE,
            "type": OperationType.TYPE,
            "input": OperationType.TYPE,
            "back": OperationType.BACK,
            "home": OperationType.HOME,
            "wait": OperationType.WAIT,
            "launch": OperationType.LAUNCH,
            "take_over": OperationType.WAIT,
            "takeover": OperationType.WAIT,
        }
        return mapping.get(value, OperationType.WAIT)

    def _extract_operation_from_text(self, text: str) -> Optional[Operation]:
        """
        Extract operation from non-JSON tool-call style responses, e.g.:
        do(action="Tap", element=[499, 651])
        """
        if not text:
            return None

        action_match = re.search(
            r'action\s*=\s*"?(?P<action>[A-Za-z_ ]+)"?',
            text,
            re.IGNORECASE,
        )
        if action_match:
            action_raw = action_match.group("action")
        else:
            simple_match = re.search(
                r"\b(?P<action>Tap|Click|Swipe|Back|Home|Wait|Type|Input|LongPress|DoubleTap|Launch)\b",
                text,
                re.IGNORECASE,
            )
            if not simple_match:
                return None
            action_raw = simple_match.group("action")

        op_type = self._normalize_operation_type(action_raw)
        params: Dict[str, Any] = {}

        element_match = re.search(
            r"element\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]",
            text,
            re.IGNORECASE,
        )
        coord_match = re.search(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
        if element_match:
            params["x"] = int(element_match.group(1))
            params["y"] = int(element_match.group(2))
        elif coord_match:
            params["x"] = int(coord_match.group(1))
            params["y"] = int(coord_match.group(2))

        start_match = re.search(
            r"start\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]",
            text,
            re.IGNORECASE,
        )
        end_match = re.search(
            r"end\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]",
            text,
            re.IGNORECASE,
        )
        if start_match and end_match:
            params["start"] = [int(start_match.group(1)), int(start_match.group(2))]
            params["end"] = [int(end_match.group(1)), int(end_match.group(2))]

        direction_match = re.search(
            r'direction\s*=\s*"?(up|down|left|right)"?',
            text,
            re.IGNORECASE,
        )
        if direction_match:
            params["direction"] = direction_match.group(1).lower()

        duration_match = re.search(
            r"duration\s*=\s*([0-9]+(?:\.[0-9]+)?)",
            text,
            re.IGNORECASE,
        )
        if duration_match:
            params["duration"] = float(duration_match.group(1))

        text_match = re.search(r'text\s*=\s*"([^"]+)"', text, re.IGNORECASE)
        if text_match:
            params["text"] = text_match.group(1)

        app_match = re.search(r'app\s*=\s*"([^"]+)"', text, re.IGNORECASE)
        if app_match:
            params["app"] = app_match.group(1)

        return Operation(
            type=op_type,
            params=params,
            description="Operation extracted from model response",
        )

    @staticmethod
    def _image_size(screenshot_data: bytes) -> Tuple[int, int]:
        """Get screenshot size, fallback to 1080x1920 if decoding fails."""
        try:
            from PIL import Image

            with Image.open(BytesIO(screenshot_data)) as image:
                return int(image.width), int(image.height)
        except Exception:
            return 1080, 1920

    @staticmethod
    def _convert_relative_point(x: int, y: int, width: int, height: int) -> Tuple[int, int]:
        """
        Convert Open-AutoGLM 0-999 coordinates to absolute pixels.
        Keep as absolute if point already looks like pixel coordinates.
        """
        if 0 <= x <= 999 and 0 <= y <= 999:
            abs_x = int((x / 999.0) * max(1, width - 1))
            abs_y = int((y / 999.0) * max(1, height - 1))
            return abs_x, abs_y
        return x, y

    def _operation_from_open_autoglm_action(
        self,
        action: Dict[str, Any],
        image_size: Tuple[int, int],
    ) -> Operation:
        """Convert Open-AutoGLM parsed action to local Operation."""
        width, height = image_size
        if action.get("_metadata") == "finish":
            return Operation(
                type=OperationType.WAIT,
                params={"duration": 1},
                description=action.get("message", "Task finished"),
            )

        action_name = str(action.get("action", "Wait"))
        op_type = self._normalize_operation_type(action_name)
        params: Dict[str, Any] = {}

        if "element" in action and isinstance(action["element"], list) and len(action["element"]) >= 2:
            x, y = self._convert_relative_point(
                int(action["element"][0]),
                int(action["element"][1]),
                width,
                height,
            )
            params["x"] = x
            params["y"] = y

        if "start" in action and "end" in action:
            start = action.get("start")
            end = action.get("end")
            if isinstance(start, list) and isinstance(end, list) and len(start) >= 2 and len(end) >= 2:
                sx, sy = self._convert_relative_point(int(start[0]), int(start[1]), width, height)
                ex, ey = self._convert_relative_point(int(end[0]), int(end[1]), width, height)
                params["start_x"] = sx
                params["start_y"] = sy
                params["end_x"] = ex
                params["end_y"] = ey

        if "duration" in action:
            duration = action.get("duration")
            if isinstance(duration, str):
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", duration)
                duration = float(m.group(1)) if m else 1.0
            params["duration"] = float(duration)

        if "text" in action:
            params["text"] = str(action.get("text", ""))
        if "app" in action:
            params["app"] = str(action.get("app", ""))

        if op_type == OperationType.WAIT and "message" in action:
            description = f"{action_name}: {action.get('message', '')}".strip()
        else:
            description = f"OpenAutoGLM action: {action_name}"
        return Operation(type=op_type, params=params, description=description)

    def analyze_screenshot(self, screenshot_data: bytes, prompt: str = "") -> str:
        """Analyze screenshot and return text description."""
        try:
            if not screenshot_data:
                return ""
            encoded_image = base64.b64encode(screenshot_data).decode("utf-8")
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt or "Describe this Android screen."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Failed to analyze screenshot: %s", e)
            return ""

    def decide_operation(
        self,
        screen_description: str,
        analysis_history: List[Dict[str, Any]],
        goal: str = "Explore the app",
    ) -> Operation:
        """
        Backward-compatible text-only operation decision path.

        This path is kept as fallback when vision-agent parsing fails.
        """
        try:
            client = self._get_client()
            history_text = ""
            for item in analysis_history[-5:]:
                history_text += f"- {item.get('operation')}: {item.get('description', '')}\n"

            prompt = f"""
You are an Android UI action planner.
Goal: {goal}

Current screen summary:
{(screen_description or '')[:1500]}

Recent operations:
{history_text}

Return exactly one JSON object only. No markdown, no prose.
Schema:
{{
  "type": "Tap|Type|Swipe|Back|Home|Wait|LongPress|DoubleTap|Launch",
  "params": {{}},
  "description": "short reason"
}}
"""

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0,
            )
            content = response.choices[0].message.content or ""

            json_str = self._extract_json_object(content)
            if json_str:
                try:
                    data = json.loads(json_str)
                    return Operation(
                        type=self._normalize_operation_type(data.get("type", "Wait")),
                        params=data.get("params", {}),
                        description=data.get("description", "AI-selected operation"),
                    )
                except json.JSONDecodeError:
                    logger.warning("JSON parse failed for decide_operation output")

            extracted = self._extract_operation_from_text(content)
            if extracted:
                return extracted
        except Exception as e:
            logger.error("Failed to decide operation: %s", e)

        return Operation(
            type=OperationType.WAIT,
            params={"duration": 2},
            description="Default wait operation on error",
        )

    def execute_operation(self, operation: Operation) -> Dict[str, Any]:
        """Return normalized operation payload for runner."""
        op_data = {
            "type": operation.type.value,
            "params": operation.params,
            "description": operation.description,
        }
        logger.info("AI Driver: %s - %s", operation.type.value, operation.description)
        return op_data

    def analyze_and_decide(
        self,
        screenshot_data: bytes,
        analysis_history: List[Dict[str, Any]],
        goal: str = "Explore the app",
    ) -> Operation:
        """
        Open-AutoGLM style one-step decision:
        image + state context -> do()/finish() action.
        """
        if not screenshot_data:
            return Operation(
                type=OperationType.WAIT,
                params={"duration": 1},
                description="Empty screenshot, wait",
            )

        current_app = ""
        if analysis_history:
            state = analysis_history[-1].get("state", {})
            if isinstance(state, dict):
                current_app = state.get("activity", "") or ""

        system_prompt = build_system_prompt_zh()
        user_text = build_screen_info(
            current_app=current_app,
            goal=goal,
            history=analysis_history,
        )
        encoded_image = base64.b64encode(screenshot_data).decode("utf-8")
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded_image}"},
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ]

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max(128, min(self.max_tokens, 3000)),
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
            )
            raw_content = response.choices[0].message.content or ""
            thinking, action_text = split_thinking_and_action(raw_content)
            logger.info("OpenAutoGLM thinking: %s", (thinking or "")[:200])

            action = parse_action(action_text)
            op = self._operation_from_open_autoglm_action(
                action=action,
                image_size=self._image_size(screenshot_data),
            )
            return op
        except Exception as exc:
            logger.warning("OpenAutoGLM action path failed, fallback to legacy parser: %s", exc)

        # Fallback path for compatibility with older/loose model outputs.
        description = self.analyze_screenshot(
            screenshot_data,
            f"Describe this Android screen for goal: {goal}",
        )
        return self.decide_operation(description, analysis_history, goal)
