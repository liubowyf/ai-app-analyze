"""Tests for stuck-task recovery script."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from scripts.recover_stuck_tasks import recover_stuck_tasks


@dataclass
class _TaskRow:
    id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    retry_count: int = 0
    error_message: str | None = None


def test_recover_stuck_tasks_dry_run_is_non_destructive():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("t1", "queued", now - timedelta(minutes=20)),
        _TaskRow("t2", "static_analyzing", now - timedelta(minutes=18), retry_count=1),
    ]
    db = MagicMock()

    with patch("scripts.recover_stuck_tasks._query_stuck_tasks", return_value=rows):
        report = recover_stuck_tasks(dry_run=True, now=now, db=db)

    assert report["mode"] == "dry-run"
    assert report["candidate_count"] == 2
    assert report["recovered_count"] == 0
    assert report["action_counts"]["queued"] == 1
    assert report["action_counts"]["retrying"] == 1
    assert rows[0].status == "queued"
    assert rows[1].status == "static_analyzing"
    db.commit.assert_not_called()


def test_recover_stuck_tasks_apply_is_idempotent():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("x1", "dynamic_analyzing", now - timedelta(minutes=25), retry_count=0),
        _TaskRow("x2", "queued", now - timedelta(minutes=10), retry_count=0),
    ]
    db = MagicMock()

    with patch("scripts.recover_stuck_tasks._query_stuck_tasks", return_value=rows):
        first = recover_stuck_tasks(dry_run=False, now=now, db=db)
    with patch("scripts.recover_stuck_tasks._query_stuck_tasks", return_value=rows):
        second = recover_stuck_tasks(dry_run=False, now=now, db=db)

    assert first["mode"] == "apply"
    assert first["recovered_count"] == 2
    assert rows[0].status == "queued"
    assert rows[0].retry_count == 1
    assert "stuck_recovered" in (rows[0].error_message or "")
    assert second["recovered_count"] == 0


def test_recover_stuck_tasks_apply_honors_batch_size_and_sleep():
    now = datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
    rows = [
        _TaskRow("b1", "dynamic_analyzing", now - timedelta(minutes=25), retry_count=0),
        _TaskRow("b2", "dynamic_analyzing", now - timedelta(minutes=24), retry_count=0),
        _TaskRow("b3", "dynamic_analyzing", now - timedelta(minutes=23), retry_count=0),
    ]
    db = MagicMock()
    slept: list[float] = []

    with patch("scripts.recover_stuck_tasks._query_stuck_tasks", return_value=rows):
        report = recover_stuck_tasks(
            dry_run=False,
            now=now,
            db=db,
            batch_size=2,
            sleep_ms=50,
            sleep_fn=lambda sec: slept.append(sec),
        )

    assert report["candidate_count"] == 2
    assert report["recovered_count"] == 2
    assert rows[0].status == "queued"
    assert rows[1].status == "queued"
    assert rows[2].status == "dynamic_analyzing"
    assert slept == [0.05]
