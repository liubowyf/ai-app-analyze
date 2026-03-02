"""Tests for dynamic analyzer retry behavior when resources are busy."""

from types import SimpleNamespace

import pytest

import workers.dynamic_analyzer as dynamic_analyzer


class Retry(Exception):
    """Retry sentinel to simulate task-runtime retry scheduling."""


class _FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first_result = first_result
        self._all_result = all_result or []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_result

    def all(self):
        return self._all_result


class _FakeSession:
    def __init__(self, task):
        self._task = task

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "Task":
            return _FakeQuery(first_result=self._task)
        return _FakeQuery(all_result=[])

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _FakeTaskContext:
    def __init__(self):
        self.request = SimpleNamespace(retries=0)
        self.called = False

    def retry(self, **kwargs):
        self.called = True
        raise Retry()


def test_run_dynamic_analysis_retries_when_no_emulator(monkeypatch):
    fake_task = SimpleNamespace(
        id="task-1",
        apk_storage_path="minio://fake.apk",
        static_analysis_result={},
        status="queued",
    )
    fake_db = _FakeSession(fake_task)
    monkeypatch.setattr(dynamic_analyzer, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(dynamic_analyzer, "start_stage_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(dynamic_analyzer, "_commit_with_retry", lambda *args, **kwargs: None)
    monkeypatch.setattr(dynamic_analyzer, "get_available_emulator", lambda task_id: None)

    retry_ctx = _FakeTaskContext()
    marked = {"called": False}
    monkeypatch.setattr(dynamic_analyzer, "_mark_task_failed", lambda *args, **kwargs: marked.__setitem__("called", True))

    with pytest.raises(Retry):
        dynamic_analyzer._run_dynamic_stage_impl("task-1", retry_context=retry_ctx)

    assert retry_ctx.called is True
    assert marked["called"] is False


def test_run_dynamic_analysis_retries_when_no_proxy_port(monkeypatch):
    fake_task = SimpleNamespace(
        id="task-2",
        apk_storage_path="minio://fake2.apk",
        static_analysis_result={},
        status="queued",
    )
    fake_db = _FakeSession(fake_task)
    release_state = {"called": False}

    monkeypatch.setattr(dynamic_analyzer, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(dynamic_analyzer, "start_stage_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(dynamic_analyzer, "_commit_with_retry", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        dynamic_analyzer,
        "get_available_emulator",
        lambda task_id: {"host": "10.16.148.66", "port": 5558, "lease_token": "abc"},
    )
    monkeypatch.setattr(
        dynamic_analyzer,
        "release_emulator",
        lambda emulator: release_state.__setitem__("called", True),
    )
    monkeypatch.setattr(dynamic_analyzer.PROXY_PORT_LEASE_MANAGER, "acquire", lambda task_id: None)

    retry_ctx = _FakeTaskContext()
    marked = {"called": False}
    monkeypatch.setattr(dynamic_analyzer, "_mark_task_failed", lambda *args, **kwargs: marked.__setitem__("called", True))

    with pytest.raises(Retry):
        dynamic_analyzer._run_dynamic_stage_impl("task-2", retry_context=retry_ctx)

    assert retry_ctx.called is True
    assert marked["called"] is False
    assert release_state["called"] is True
