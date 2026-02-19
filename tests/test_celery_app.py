"""Test Celery app configuration."""


def test_celery_app_created():
    """Test that Celery app is created."""
    from workers.celery_app import celery_app

    assert celery_app is not None
    assert celery_app.main == "workers"


def test_celery_config():
    """Test Celery configuration."""
    from workers.celery_app import celery_app

    assert "broker_url" in celery_app.conf
    assert "result_backend" in celery_app.conf
