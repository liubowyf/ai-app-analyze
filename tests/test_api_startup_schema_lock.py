from types import SimpleNamespace

import pytest

import core.database as database


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _Connection:
    def __init__(self, lock_value=1):
        self.lock_value = lock_value
        self.executed = []
        self.commits = 0

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params))
        if "GET_LOCK" in sql:
            return _Result(self.lock_value)
        return _Result(1)

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return self.connection


def test_ensure_schema_ready_uses_advisory_lock(monkeypatch):
    connection = _Connection(lock_value=1)
    create_all_calls = []

    monkeypatch.setattr(database, "engine", _Engine(connection))
    monkeypatch.setattr(
        database,
        "Base",
        SimpleNamespace(
            metadata=SimpleNamespace(
                create_all=lambda bind: create_all_calls.append(bind)
            )
        ),
    )

    database.ensure_schema_ready()

    assert create_all_calls == [connection]
    executed_sql = [sql for sql, _ in connection.executed]
    assert any("GET_LOCK" in sql for sql in executed_sql)
    assert any("RELEASE_LOCK" in sql for sql in executed_sql)


def test_ensure_schema_ready_raises_when_lock_not_acquired(monkeypatch):
    connection = _Connection(lock_value=0)
    monkeypatch.setattr(database, "engine", _Engine(connection))
    monkeypatch.setattr(
        database,
        "Base",
        SimpleNamespace(metadata=SimpleNamespace(create_all=lambda bind: None)),
    )

    with pytest.raises(RuntimeError, match="schema initialization lock"):
        database.ensure_schema_ready()
