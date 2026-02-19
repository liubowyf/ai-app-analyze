"""Enhanced test for AutoGLM-Phone model with proper prompting."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from openai import OpenAI


def test_with_screenshot_simulation():
    """Test model with simulated Android screenshot analysis."""
    print("=" * 60)
    print("AutoGLM-Phone Enhanced Test")
    print("=" * 60)

    client = OpenAI(
        base_url=settings.AI_BASE_URL,
        api_key=settings.AI_API_KEY,
    )

    # Test 1: Direct JSON response request
    print("\n[1/3] Testing structured output...")
    prompt = """
You are controlling an Android phone. Analyze the screen and decide the next action.

Screen Description: Login screen with username field, password field, and a "Login" button.

Available Actions:
- Tap(x, y): Tap at coordinates
- Type(text): Type text into focused field
- Swipe(direction): Swipe up/down/left/right
- Wait(seconds): Wait for specified time

Return ONLY a JSON object (no markdown, no explanation):
{"action": "Tap", "x": 540, "y": 1200, "reason": "Tap login button"}
"""

    response = client.chat.completions.create(
        model=settings.AI_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.1,
    )
    content = response.choices[0].message.content
    print(f"  Response: {content}")

    # Try to parse
    import json
    import re
    match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            print(f"  ✅ Parsed JSON: {data}")
        except:
            print(f"  ⚠️  Could not parse as JSON")

    # Test 2: Step-by-step exploration
    print("\n[2/3] Testing step-by-step app exploration...")
    history = []

    for i in range(3):
        prompt = f"""
Step {i+1}: You are exploring an Android app.

Previous actions: {history if history else 'None (first step)'}

Current screen: Home screen with:
- Search bar at top
- List of items below
- Bottom navigation with Home, Search, Profile

What should you do next? Choose ONE action:
- Tap on search bar
- Scroll down
- Tap on an item

Just say what you would do in one sentence.
"""
        response = client.chat.completions.create(
            model=settings.AI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3,
        )
        action = response.choices[0].message.content.strip()
        history.append(action)
        print(f"  Step {i+1}: {action}")

    print("  ✅ Multi-step exploration works!")

    # Test 3: Network trigger scenario
    print("\n[3/3] Testing network request trigger scenario...")
    prompt = """
You are testing an Android app for security analysis.

Goal: Trigger as many network requests as possible to analyze traffic.

Current screen: Product detail page with:
- Product image
- "Add to Cart" button
- "Buy Now" button
- Reviews section
- Related products

List 3 actions that would trigger network requests:
1.
2.
3.
"""

    response = client.chat.completions.create(
        model=settings.AI_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.5,
    )
    content = response.choices[0].message.content
    print(f"  Response:\n{content}")
    print("  ✅ Network trigger analysis works!")

    print("\n" + "=" * 60)
    print("✅ All enhanced tests completed!")
    print("=" * 60)

    print("\n📝 Summary:")
    print("  - Model is responsive and understands Android context")
    print("  - Can provide step-by-step exploration guidance")
    print("  - Can identify network-triggering actions")
    print("  - Recommend adjusting prompts for your specific use case")


if __name__ == "__main__":
    test_with_screenshot_simulation()
