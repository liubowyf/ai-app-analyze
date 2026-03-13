from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.exc import OperationalError


class _FakeDeleteQuery:
    def filter(self, *args, **kwargs):
        return self

    def delete(self, synchronize_session=False):
        return 0


class _FakePersistSession:
    def __init__(self, commit_error: Exception | None = None):
        self.commit_error = commit_error
        self.rollback_called = False
        self.closed = False
        self.added = []
        self.commits = 0

    def query(self, model):
        return _FakeDeleteQuery()

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            error = self.commit_error
            self.commit_error = None
            raise error

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


class _FakeTrafficMonitor:
    def get_requests_as_dict(self):
        return [
            {
                "url": "https://example.com/api",
                "method": "GET",
                "host": "example.com",
                "ip": "1.1.1.1",
                "hit_count": 2,
                "source_type": "conn",
                "capture_mode": "redroid_zeek",
            }
        ]

    def get_candidate_requests_as_dict(self):
        return []

    def analyze_traffic(self):
        return {
            "capture_mode": "redroid_zeek",
            "source_breakdown": {"conn": 2},
        }

    def get_domain_stats(self):
        return [
            {
                "domain": "example.com",
                "hit_count": 2,
                "first_seen_at": "2026-03-13T10:00:00",
                "last_seen_at": "2026-03-13T10:05:00",
                "source_types": ["conn"],
            }
        ]


def test_persist_dynamic_normalized_tables_rebuilds_rows_after_deadlock(monkeypatch):
    from workers import dynamic_analyzer
    from core import database as database_module

    deadlock = OperationalError(
        "INSERT INTO dynamic_analysis ...",
        {},
        Exception(1213, "Deadlock found when trying to get lock; try restarting transaction"),
    )
    first_session = _FakePersistSession(commit_error=deadlock)
    second_session = _FakePersistSession()
    sessions = iter([first_session, second_session])

    monkeypatch.setattr(dynamic_analyzer, "SessionLocal", lambda: next(sessions))
    monkeypatch.setattr(database_module.Base.metadata, "create_all", lambda *args, **kwargs: None)
    monkeypatch.setattr(dynamic_analyzer.time, "sleep", lambda *_args, **_kwargs: None)

    exploration_result = SimpleNamespace(
        total_steps=3,
        phases_completed=["setup", "explore"],
        activities_visited=["com.demo/.MainActivity"],
        screenshots=[
            {
                "stage": "launch",
                "description": "ready",
                "storage_path": "screenshots/demo.png",
                "timestamp": "2026-03-13T10:01:00",
            }
        ],
        success=True,
        error_message=None,
    )

    dynamic_analyzer._persist_dynamic_normalized_tables(
        db=None,
        task_id="task-deadlock-1",
        package_name="com.demo.app",
        exploration_result=exploration_result,
        traffic_monitor=_FakeTrafficMonitor(),
        domain_report={
            "master_domains": [
                {
                    "domain": "example.com",
                    "ip": "1.1.1.1",
                    "score": 2,
                    "confidence": "observed",
                    "request_count": 2,
                }
            ]
        },
        retries=1,
        retry_delay=0,
    )

    assert first_session.rollback_called is True
    assert second_session.rollback_called is False
    assert second_session.commits == 1
    assert first_session.closed is True
    assert second_session.closed is True
    assert len(first_session.added) > 0
    assert len(second_session.added) > 0
