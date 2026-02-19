"""Initialize database tables."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import engine, Base
from models.task import Task
from models.whitelist import WhitelistRule


def init_database():
    """Create all database tables."""
    print("Creating database tables...")

    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)

        print("✅ Database tables created successfully!")
        print("\nCreated tables:")
        for table in Base.metadata.tables:
            print(f"  - {table}")

    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

    return True


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
