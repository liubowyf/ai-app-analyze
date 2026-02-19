"""Test AutoGLM-Phone model connection and functionality."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import settings


def test_model_connection():
    """Test basic connection to AutoGLM-Phone model."""
    print("=" * 60)
    print("AutoGLM-Phone Model Connection Test")
    print("=" * 60)
    print(f"\nModel Configuration:")
    print(f"  Base URL: {settings.AI_BASE_URL}")
    print(f"  Model Name: {settings.AI_MODEL_NAME}")
    print(f"  API Key: {settings.AI_API_KEY}")

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
        )

        print("\n[1/3] Testing text completion...")
        response = client.chat.completions.create(
            model=settings.AI_MODEL_NAME,
            messages=[
                {"role": "user", "content": "Hello, are you AutoGLM-Phone? Please introduce yourself briefly."}
            ],
            max_tokens=100,
            temperature=0.1,
        )
        print(f"  Response: {response.choices[0].message.content}")
        print("  ✅ Text completion works!")

        print("\n[2/3] Testing model info...")
        try:
            models = client.models.list()
            print(f"  Available models: {[m.id for m in models.data]}")
            print("  ✅ Model list retrieved!")
        except Exception as e:
            print(f"  ⚠️  Model list not available: {e}")

        print("\n[3/3] Testing Android screen analysis prompt...")
        test_prompt = """
You are analyzing an Android application screen. Given the screen description below,
decide the next action to explore the app.

Screen: Home screen with a login button at the top, a search bar in the middle,
and three menu items at the bottom (Home, Search, Profile).

Goal: Explore the app and trigger network requests.

What action should be taken next? Return JSON format:
{"type": "Tap", "params": {"x": 100, "y": 200}, "description": "reason"}
"""
        response = client.chat.completions.create(
            model=settings.AI_MODEL_NAME,
            messages=[{"role": "user", "content": test_prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        print(f"  Response: {response.choices[0].message.content[:200]}...")
        print("  ✅ Android analysis prompt works!")

        print("\n" + "=" * 60)
        print("✅ All tests passed! AutoGLM-Phone is ready.")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"\nTroubleshooting:")
        print(f"  1. Check if the model server is running at {settings.AI_BASE_URL}")
        print(f"  2. Verify the model ID is correct: {settings.AI_MODEL_NAME}")
        print(f"  3. Check network connectivity to 10.16.148.66:6000")
        return False


def test_ai_driver():
    """Test the AI Driver module with the configured model."""
    print("\n" + "=" * 60)
    print("AI Driver Module Test")
    print("=" * 60)

    try:
        from modules.ai_driver import AIDriver, OperationType

        driver = AIDriver(
            base_url=settings.AI_BASE_URL,
            model_name=settings.AI_MODEL_NAME,
            api_key=settings.AI_API_KEY,
        )

        print("\n[1/2] Testing operation decision...")
        operation = driver.decide_operation(
            screen_description="Android home screen with app icons",
            analysis_history=[],
            goal="Find and open the settings app"
        )
        print(f"  Operation: {operation.type.value}")
        print(f"  Params: {operation.params}")
        print(f"  Description: {operation.description}")
        print("  ✅ Operation decision works!")

        print("\n[2/2] Testing operation execution...")
        op_data = driver.execute_operation(operation)
        print(f"  Operation data: {op_data}")
        print("  ✅ Operation execution works!")

        print("\n" + "=" * 60)
        print("✅ AI Driver module is working correctly!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = test_model_connection()
    if success:
        test_ai_driver()
