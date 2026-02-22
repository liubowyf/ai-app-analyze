"""Tests for distributed emulator lease manager."""

from modules.emulator_pool.lease import EmulatorLeaseManager


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)
        return 1


def test_lease_manager_acquire_and_release(monkeypatch):
    manager = EmulatorLeaseManager(redis_url="redis://fake:6379/0", lease_ttl_seconds=120)
    fake = _FakeRedis()
    monkeypatch.setattr(manager, "_get_client", lambda: fake)

    leased = manager.acquire(
        task_id="task-1",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased is not None
    assert leased["host"] == "10.0.0.1"
    assert leased["port"] == 5555
    assert "lease_key" in leased
    assert "lease_token" in leased

    # Same emulator cannot be re-acquired while leased.
    leased_again = manager.acquire(
        task_id="task-2",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased_again is None

    released = manager.release(leased)
    assert released is True

    leased_after_release = manager.acquire(
        task_id="task-3",
        candidates=[{"host": "10.0.0.1", "port": 5555}],
    )
    assert leased_after_release is not None


def test_lease_manager_release_with_mismatched_token(monkeypatch):
    manager = EmulatorLeaseManager(redis_url="redis://fake:6379/0", lease_ttl_seconds=120)
    fake = _FakeRedis()
    monkeypatch.setattr(manager, "_get_client", lambda: fake)

    leased = manager.acquire(
        task_id="task-1",
        candidates=[{"host": "10.0.0.2", "port": 5556}],
    )
    assert leased is not None

    ok = manager.release(
        {
            "host": leased["host"],
            "port": leased["port"],
            "lease_key": leased["lease_key"],
            "lease_token": "wrong-token",
        }
    )
    assert ok is False
