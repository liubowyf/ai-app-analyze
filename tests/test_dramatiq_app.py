"""Test Dramatiq app bootstrap."""


def test_dramatiq_module_exports_runtime_flags():
    from workers import dramatiq_app

    assert hasattr(dramatiq_app, "dramatiq")
    assert hasattr(dramatiq_app, "dramatiq_broker")
    assert callable(dramatiq_app.is_dramatiq_ready)

