"""Backend switch tests for dynamic analyzer."""

from __future__ import annotations

from types import SimpleNamespace


def test_dynamic_backend_defaults_to_redroid_remote(monkeypatch):
    """Default backend should dispatch to the redroid adapter."""
    from workers import dynamic_analyzer

    calls: list[tuple[str, str, object | None]] = []

    class FakeBackend:
        backend_name = "redroid_remote"

        def run(self, task_id: str, retry_context: object | None = None) -> dict:
            calls.append((self.backend_name, task_id, retry_context))
            return {"status": "success", "backend": self.backend_name}

    monkeypatch.setattr(dynamic_analyzer, "settings", SimpleNamespace(ANALYSIS_BACKEND="redroid_remote"))
    monkeypatch.setattr(dynamic_analyzer, "_build_dynamic_backend", lambda backend_name: FakeBackend())

    result = dynamic_analyzer._run_dynamic_stage_impl("task-redroid-default", retry_context=None)

    assert result["backend"] == "redroid_remote"
    assert calls == [("redroid_remote", "task-redroid-default", None)]


def test_dynamic_backend_dispatches_to_redroid_remote(monkeypatch):
    """Configured redroid backend should dispatch to redroid adapter."""
    from workers import dynamic_analyzer

    calls: list[tuple[str, str, object | None]] = []
    retry_context = object()

    class FakeBackend:
        backend_name = "redroid_remote"

        def run(self, task_id: str, retry_context: object | None = None) -> dict:
            calls.append((self.backend_name, task_id, retry_context))
            return {"status": "success", "backend": self.backend_name}

    monkeypatch.setattr(dynamic_analyzer, "settings", SimpleNamespace(ANALYSIS_BACKEND="redroid_remote"))
    monkeypatch.setattr(dynamic_analyzer, "_build_dynamic_backend", lambda backend_name: FakeBackend())

    result = dynamic_analyzer._run_dynamic_stage_impl("task-redroid", retry_context=retry_context)

    assert result["backend"] == "redroid_remote"
    assert calls == [("redroid_remote", "task-redroid", retry_context)]
