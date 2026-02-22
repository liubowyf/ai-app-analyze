"""AI Driver module for Android automation using OpenAI-compatible APIs."""
import base64
import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from core.config import settings

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
    """AI driver for Android automation using OpenAI API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ):
        """
        Initialize AI driver.

        Args:
            base_url: OpenAI-compatible API base URL
            model_name: Model name to use
            api_key: API key (default: EMPTY for local models)
            request_timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.AI_BASE_URL
        self.model_name = model_name or settings.AI_MODEL_NAME
        self.api_key = api_key or settings.AI_API_KEY
        if request_timeout is None:
            try:
                request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
            except ValueError:
                request_timeout = 30.0
        self.request_timeout = max(3.0, min(float(request_timeout), 180.0))
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

    def analyze_screenshot(self, screenshot_data: bytes, prompt: str = "") -> str:
        """
        Analyze screenshot and return description.

        Args:
            screenshot_data: Screenshot image data
            prompt: Additional prompt context

        Returns:
            Text description of the screenshot
        """
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
                            {
                                "type": "text",
                                "text": prompt or "Describe this Android screen. What UI elements are visible?",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Failed to analyze screenshot: {e}")
            return ""

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
        """Normalize LLM operation type text into supported enum value."""
        value = (raw_type or "").strip().lower()
        mapping = {
            "tap": OperationType.TAP,
            "click": OperationType.TAP,
            "doubletap": OperationType.DOUBLE_TAP,
            "double_tap": OperationType.DOUBLE_TAP,
            "longpress": OperationType.LONG_PRESS,
            "long_press": OperationType.LONG_PRESS,
            "swipe": OperationType.SWIPE,
            "type": OperationType.TYPE,
            "input": OperationType.TYPE,
            "back": OperationType.BACK,
            "home": OperationType.HOME,
            "wait": OperationType.WAIT,
            "launch": OperationType.LAUNCH,
        }
        return mapping.get(value, OperationType.WAIT)

    def _extract_operation_from_text(self, text: str) -> Optional[Operation]:
        """
        Extract operation from non-JSON tool-call style responses, e.g.:
        do(action="Tap", element=[499, 651])
        """
        if not text:
            return None

        action_match = re.search(r'action\s*=\s*"?(?P<action>[A-Za-z_]+)"?', text, re.IGNORECASE)
        if action_match:
            action_raw = action_match.group("action")
        else:
            # Also accept simple tool output like: "Tap: (499, 526)"
            simple_match = re.search(
                r"\b(?P<action>Tap|Click|Swipe|Back|Home|Wait|Type|Input|LongPress|DoubleTap)\b",
                text,
                re.IGNORECASE,
            )
            if not simple_match:
                return None
            action_raw = simple_match.group("action")

        op_type = self._normalize_operation_type(action_raw)
        params: Dict[str, Any] = {}

        # Coordinates from element=[x,y] or coordinate tuples like (x, y)
        element_match = re.search(r"element\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]", text, re.IGNORECASE)
        coord_match = re.search(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
        if element_match:
            params["x"] = int(element_match.group(1))
            params["y"] = int(element_match.group(2))
        elif coord_match:
            params["x"] = int(coord_match.group(1))
            params["y"] = int(coord_match.group(2))

        direction_match = re.search(r'direction\s*=\s*"?(up|down|left|right)"?', text, re.IGNORECASE)
        if direction_match:
            params["direction"] = direction_match.group(1).lower()

        duration_match = re.search(r"duration\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
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
            description="Operation extracted from AI tool-call response",
        )

    def decide_operation(self, screen_description: str,
                        analysis_history: List[Dict[str, Any]],
                        goal: str = "Explore the app") -> Operation:
        """
        Decide next operation based on screen and history.

        Args:
            screen_description: Description of current screen
            analysis_history: History of previous operations and results
            goal: Goal to achieve

        Returns:
            Operation to execute
        """
        try:
            client = self._get_client()

            # Build compact context from recent operations.
            history_text = ""
            for item in analysis_history[-5:]:
                history_text += f"- {item.get('operation')}: {item.get('description', '')}\n"

            screen_description = (screen_description or "")[:1500]

            prompt = f"""
You are an Android UI action planner.
Goal: {goal}

Current screen summary:
{screen_description}

Recent operations:
{history_text}

Return exactly one JSON object only. No markdown, no prose.
Schema:
{{
  "type": "Tap|Type|Swipe|Back|Home|Wait|LongPress|DoubleTap|Launch",
  "params": {{}},
  "description": "short reason"
}}

Rules:
1) Prefer Tap/Swipe over Launch.
2) If Tap, include integer x,y in visible screen range.
3) If Wait, set duration between 1 and 4.
4) Never output any text outside JSON.
"""

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0,
            )

            content = response.choices[0].message.content or ""
            logger.info(f"AI response: {content}")

            json_str = self._extract_json_object(content)

            if json_str:
                try:
                    data = json.loads(json_str)
                    op_type = self._normalize_operation_type(data.get("type", "Wait"))
                    return Operation(
                        type=op_type,
                        params=data.get("params", {}),
                        description=data.get("description", "AI-selected operation"),
                    )
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse JSON: {je}")
                    logger.error(f"JSON string was: {json_str}")

            extracted = self._extract_operation_from_text(content)
            if extracted:
                return extracted

        except Exception as e:
            logger.error(f"Failed to decide operation: {e}")

        # Default to wait on error
        return Operation(
            type=OperationType.WAIT,
            params={"duration": 2},
            description="Default wait operation on error",
        )

    def execute_operation(self, operation: Operation) -> Dict[str, Any]:
        """
        Execute operation on Android device (returns operation data for runner).

        Args:
            operation: Operation to execute

        Returns:
            Operation data for device runner
        """
        op_data = {
            "type": operation.type.value,
            "params": operation.params,
            "description": operation.description,
        }
        logger.info(f"AI Driver: {operation.type.value} - {operation.description}")
        return op_data

    def analyze_and_decide(self, screenshot_data: bytes,
                          analysis_history: List[Dict[str, Any]],
                          goal: str = "Explore the app") -> Operation:
        """
        Analyze screenshot and decide next operation in one call.

        Args:
            screenshot_data: Screenshot image data
            analysis_history: History of previous operations
            goal: Goal to achieve

        Returns:
            Operation to execute
        """
        description = self.analyze_screenshot(screenshot_data, f"Describe this Android screen for goal: {goal}")
        return self.decide_operation(description, analysis_history, goal)
