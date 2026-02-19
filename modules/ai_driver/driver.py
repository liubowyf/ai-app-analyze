"""AI Driver module for Android automation using OpenAI-compatible APIs."""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

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

    def __init__(self, base_url: str = "http://localhost:8000/v1",
                 model_name: str = "autoglm-phone-9b",
                 api_key: str = "EMPTY"):
        """
        Initialize AI driver.

        Args:
            base_url: OpenAI-compatible API base URL
            model_name: Model name to use
            api_key: API key (default: EMPTY for local models)
        """
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key
        self.client: Optional[Any] = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self.client is None:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
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
                                    "url": f"data:image/png;base64,{screenshot_data.hex()}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to analyze screenshot: {e}")
            return ""

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

            # Build context from history
            history_text = ""
            for item in analysis_history[-5:]:  # Last 5 operations
                history_text += f"- {item.get('operation')}: {item.get('result', '')}\n"

            prompt = f"""
Current screen: {screen_description}

Recent operations:
{history_text}

Goal: {goal}

Based on the screen description and goal, decide the next operation.
Return JSON with:
{{
    "type": "Tap|Type|Swipe|Back|Home|Wait|LongPress|DoubleTap|Launch",
    "params": {{"x": x, "y": y}} for Tap, or {{"text": "text"}} for Type, or {{"direction": "up|down|left|right"}} for Swipe, or {{"duration": seconds}} for Wait,
    "description": "Why you chose this operation"
}}
"""

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            # Parse JSON from response
            import json
            import re

            # Extract JSON from markdown if present
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return Operation(
                    type=OperationType(data.get("type", "Wait")),
                    params=data.get("params", {}),
                    description=data.get("description", ""),
                )

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
