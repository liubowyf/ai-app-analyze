"""Integration test for all services."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import settings


def test_mysql_connection():
    """Test MySQL database connection."""
    print("\n[1/5] Testing MySQL connection...")
    print(f"  Host: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
    print(f"  Database: {settings.MYSQL_DATABASE}")
    print(f"  User: {settings.MYSQL_USER}")

    try:
        import pymysql
        import ssl

        # Create SSL context (skip verification for testing)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            connect_timeout=5,
            ssl=ssl_context
        )
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"  ✅ MySQL connected! Version: {version[0]}")
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ MySQL connection failed: {e}")
        return False


def test_redis_connection():
    """Test Redis connection."""
    print("\n[2/5] Testing Redis connection...")
    print(f"  Host: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    try:
        import redis
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        r.ping()
        print("  ✅ Redis connected!")

        # Test set/get
        r.set("test_key", "test_value", ex=10)
        value = r.get("test_key")
        print(f"  Test set/get: {value}")
        return True
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        return False


def test_ai_model_connection():
    """Test AutoGLM-Phone model connection."""
    print("\n[3/5] Testing AI Model connection...")
    print(f"  URL: {settings.AI_BASE_URL}")
    print(f"  Model: {settings.AI_MODEL_NAME}")

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
        )
        response = client.chat.completions.create(
            model=settings.AI_MODEL_NAME,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=20,
        )
        print(f"  ✅ AI Model connected!")
        print(f"  Response: {response.choices[0].message.content[:50]}...")
        return True
    except Exception as e:
        print(f"  ❌ AI Model connection failed: {e}")
        return False


def test_android_emulators():
    """Test Android emulator ADB connections."""
    print("\n[4/5] Testing Android Emulators...")

    results = []
    for i, emulator in enumerate(settings.android_emulators, 1):
        host, port = emulator.split(":")
        print(f"  Emulator {i}: {emulator}")

        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, int(port)))
            sock.close()

            if result == 0:
                print(f"    ✅ Port {port} is open")
                results.append(True)
            else:
                print(f"    ❌ Port {port} is closed")
                results.append(False)
        except Exception as e:
            print(f"    ❌ Connection error: {e}")
            results.append(False)

    return any(results)


def test_database_tables():
    """Test if required database tables exist."""
    print("\n[5/5] Testing database tables...")

    try:
        import pymysql
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            ssl=ssl_context
        )
        cursor = conn.cursor()

        # Check required tables
        required_tables = ["tasks", "network_whitelist"]
        existing_tables = []

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]

        for table in required_tables:
            if table in table_names:
                print(f"  ✅ Table '{table}' exists")
                existing_tables.append(table)
            else:
                print(f"  ⚠️  Table '{table}' does not exist (needs migration)")

        conn.close()
        return len(existing_tables) > 0
    except Exception as e:
        print(f"  ❌ Database check failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("APK Analysis Platform - Integration Test")
    print("=" * 60)
    print("\nConfiguration:")
    print(f"  MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    print(f"  Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"  AI Model: {settings.AI_BASE_URL}")
    print(f"  Android Emulators: {len(settings.android_emulators)} instances")

    results = {
        "MySQL": test_mysql_connection(),
        "Redis": test_redis_connection(),
        "AI Model": test_ai_model_connection(),
        "Android Emulators": test_android_emulators(),
        "Database Tables": test_database_tables(),
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("✅ All services are ready!")
    else:
        print("⚠️  Some services need attention")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
