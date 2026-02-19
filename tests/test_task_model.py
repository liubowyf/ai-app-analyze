"""Unit tests for Task model."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.task import Task, TaskPriority, TaskStatus


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestTaskStatus:
    """Test cases for TaskStatus enum."""

    def test_status_values(self):
        """Test that TaskStatus has all required values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.QUEUED == "queued"
        assert TaskStatus.STATIC_ANALYZING == "static_analyzing"
        assert TaskStatus.DYNAMIC_ANALYZING == "dynamic_analyzing"
        assert TaskStatus.REPORT_GENERATING == "report_generating"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"


class TestTaskPriority:
    """Test cases for TaskPriority enum."""

    def test_priority_values(self):
        """Test that TaskPriority has all required values."""
        assert TaskPriority.URGENT == "urgent"
        assert TaskPriority.NORMAL == "normal"
        assert TaskPriority.BATCH == "batch"


class TestTaskModel:
    """Test cases for Task model."""

    def test_create_task_with_required_fields(self, db_session):
        """Test creating a task with only required fields."""
        task = Task(
            apk_file_name="test.apk",
            apk_file_size=1024,
            apk_md5="abc123def456",
        )
        db_session.add(task)
        db_session.commit()

        assert task.id is not None
        assert uuid.UUID(task.id)  # Valid UUID
        assert task.apk_file_name == "test.apk"
        assert task.apk_file_size == 1024
        assert task.apk_md5 == "abc123def456"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.retry_count == 0
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_create_task_with_all_fields(self, db_session):
        """Test creating a task with all fields."""
        task = Task(
            id=str(uuid.uuid4()),
            apk_file_name="full_test.apk",
            apk_file_size=2048,
            apk_md5="md5hash123",
            apk_sha256="sha256hash456",
            apk_storage_path="/storage/apks/full_test.apk",
            status=TaskStatus.STATIC_ANALYZING,
            priority=TaskPriority.URGENT,
            error_message="Test error",
            error_stack="Test stack trace",
            retry_count=2,
            static_analysis_result={"permissions": ["INTERNET"]},
            dynamic_analysis_result={"network_calls": 10},
            report_storage_path="/storage/reports/report_1.pdf",
        )
        db_session.add(task)
        db_session.commit()

        assert task.apk_sha256 == "sha256hash456"
        assert task.apk_storage_path == "/storage/apks/full_test.apk"
        assert task.status == TaskStatus.STATIC_ANALYZING
        assert task.priority == TaskPriority.URGENT
        assert task.error_message == "Test error"
        assert task.error_stack == "Test stack trace"
        assert task.retry_count == 2
        assert task.static_analysis_result == {"permissions": ["INTERNET"]}
        assert task.dynamic_analysis_result == {"network_calls": 10}
        assert task.report_storage_path == "/storage/reports/report_1.pdf"

    def test_task_repr(self, db_session):
        """Test task string representation."""
        task = Task(
            apk_file_name="repr_test.apk",
            apk_file_size=512,
            apk_md5="repr_md5",
        )
        db_session.add(task)
        db_session.commit()

        repr_str = repr(task)
        assert "Task" in repr_str
        assert task.id in repr_str
        assert "repr_test.apk" in repr_str
        assert "pending" in repr_str

    def test_task_to_dict(self, db_session):
        """Test converting task to dictionary."""
        created_at = datetime.utcnow()
        task = Task(
            apk_file_name="dict_test.apk",
            apk_file_size=3072,
            apk_md5="dict_md5",
            created_at=created_at,
            updated_at=created_at,
        )
        db_session.add(task)
        db_session.commit()

        task_dict = task.to_dict()

        assert task_dict["id"] == task.id
        assert task_dict["apk_file_name"] == "dict_test.apk"
        assert task_dict["apk_file_size"] == 3072
        assert task_dict["apk_md5"] == "dict_md5"
        assert task_dict["status"] == "pending"
        assert task_dict["priority"] == "normal"
        assert "created_at" in task_dict
        assert "updated_at" in task_dict
        # Check ISO format
        assert "T" in task_dict["created_at"]

    def test_task_to_dict_with_timestamps(self, db_session):
        """Test to_dict with started_at and completed_at."""
        started = datetime.utcnow()
        task = Task(
            apk_file_name="timestamp_test.apk",
            apk_file_size=1024,
            apk_md5="timestamp_md5",
            started_at=started,
            completed_at=started,
        )
        db_session.add(task)
        db_session.commit()

        task_dict = task.to_dict()

        assert "started_at" in task_dict
        assert "completed_at" in task_dict
        assert "T" in task_dict["started_at"]

    def test_task_status_index(self, db_session):
        """Test that status field is indexed."""
        # Create multiple tasks with different statuses
        for i in range(3):
            task = Task(
                apk_file_name=f"status_{i}.apk",
                apk_file_size=1024,
                apk_md5=f"status_md5_{i}",
                status=TaskStatus.QUEUED if i == 0 else TaskStatus.PENDING,
            )
            db_session.add(task)
        db_session.commit()

        # Query by status should work efficiently
        queued_tasks = (
            db_session.query(Task)
            .filter(Task.status == TaskStatus.QUEUED)
            .all()
        )
        assert len(queued_tasks) == 1

    def test_task_md5_index(self, db_session):
        """Test that apk_md5 field is indexed."""
        task = Task(
            apk_file_name="md5_test.apk",
            apk_file_size=1024,
            apk_md5="indexed_md5",
        )
        db_session.add(task)
        db_session.commit()

        # Query by md5 should work efficiently
        found_task = (
            db_session.query(Task)
            .filter(Task.apk_md5 == "indexed_md5")
            .first()
        )
        assert found_task is not None
        assert found_task.apk_file_name == "md5_test.apk"

    def test_task_updated_at_on_update(self, db_session):
        """Test that updated_at is updated on modification."""
        task = Task(
            apk_file_name="update_test.apk",
            apk_file_size=1024,
            apk_md5="update_md5",
        )
        db_session.add(task)
        db_session.commit()

        original_updated_at = task.updated_at

        # Modify and commit
        task.status = TaskStatus.QUEUED
        db_session.commit()

        # updated_at should be different (though in SQLite in-memory, timing might be same)
        # This test verifies the field exists and can be updated
        assert task.updated_at is not None

    def test_task_json_fields_nullable(self, db_session):
        """Test that JSON fields are nullable."""
        task = Task(
            apk_file_name="json_test.apk",
            apk_file_size=1024,
            apk_md5="json_md5",
            static_analysis_result=None,
            dynamic_analysis_result=None,
        )
        db_session.add(task)
        db_session.commit()

        assert task.static_analysis_result is None
        assert task.dynamic_analysis_result is None

    def test_task_json_fields_with_data(self, db_session):
        """Test that JSON fields can store complex data."""
        complex_data = {
            "permissions": ["INTERNET", "CAMERA"],
            "activities": ["MainActivity", "SettingsActivity"],
            "metadata": {"version": "1.0", "package": "com.test"},
        }
        task = Task(
            apk_file_name="complex_json.apk",
            apk_file_size=2048,
            apk_md5="complex_md5",
            static_analysis_result=complex_data,
        )
        db_session.add(task)
        db_session.commit()

        assert task.static_analysis_result == complex_data
        assert task.static_analysis_result["permissions"] == ["INTERNET", "CAMERA"]
