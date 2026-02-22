"""Runtime behavior tests for mitmproxy integration."""
import logging
from types import SimpleNamespace

import modules.traffic_monitor.mitmproxy_integration as integration


class _DummyAddons:
    def __init__(self):
        self.added = []

    def add(self, addon):
        self.added.append(addon)


class _DummyMaster:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.addons = _DummyAddons()
        self.shutdown_called = False

    async def run(self):
        return None

    def shutdown(self):
        self.shutdown_called = True


def test_start_proxy_starts_background_thread(monkeypatch):
    """MitmProxyManager.start_proxy should create master and start daemon thread."""
    holder = {}

    def fake_dumpmaster(*args, **kwargs):
        master = _DummyMaster(*args, **kwargs)
        holder["master"] = master
        return master

    class DummyThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

        def is_alive(self):
            return self.started

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(integration, "DumpMaster", fake_dumpmaster)
    monkeypatch.setattr(integration.threading, "Thread", DummyThread)

    manager = integration.MitmProxyManager()
    manager.start_proxy(port=9090, request_callback=None)

    assert manager.is_running is True
    assert manager.proxy_port == 9090
    assert isinstance(manager.collector, integration.TrafficCollector)
    assert len(holder["master"].addons.added) == 1
    assert "loop" in holder["master"].kwargs


def test_resolve_proxy_host_prefers_env_override(monkeypatch):
    """Explicit env var should override auto-detected host."""
    monkeypatch.setenv("MITMPROXY_HOST", "10.9.8.7")

    resolved = integration._resolve_proxy_host("10.16.148.66")

    assert resolved == "10.9.8.7"


def test_configure_android_proxy_uses_resolved_host(monkeypatch):
    """When adb reverse fails, Android proxy command should use resolved host."""
    commands = []

    class FakeRunner:
        def execute_adb_remote(self, host, port, cmd):
            commands.append((host, port, cmd))
            if cmd.startswith("reverse "):
                return "error: device offline"
            if "settings get global http_proxy" in cmd:
                return "10.0.0.9:8080"
            return "ok"

    monkeypatch.setattr(integration, "_resolve_proxy_host", lambda _: "10.0.0.9")
    monkeypatch.setattr(
        "modules.android_runner.AndroidRunner",  # string form for import-time lookup
        FakeRunner,
    )

    ok = integration.configure_android_proxy("10.16.148.66", 5555, 8080)

    assert ok is True
    assert any("settings put global http_proxy 10.0.0.9:8080" in cmd for _, _, cmd in commands)


def test_configure_android_proxy_prefers_localhost_when_reverse_works(monkeypatch):
    """When adb reverse succeeds, proxy should be set to 127.0.0.1."""
    commands = []

    class FakeRunner:
        def execute_adb_remote(self, host, port, cmd):
            commands.append((host, port, cmd))
            if "settings get global http_proxy" in cmd:
                return "127.0.0.1:8080"
            return "ok"

    monkeypatch.setattr(
        "modules.android_runner.AndroidRunner",
        FakeRunner,
    )

    ok = integration.configure_android_proxy("10.16.148.66", 5555, 8080)

    assert ok is True
    assert any(cmd.startswith("reverse tcp:8080 tcp:8080") for _, _, cmd in commands)
    assert any("settings put global http_proxy 127.0.0.1:8080" in cmd for _, _, cmd in commands)


def test_detach_mitmproxy_handlers_removes_mitm_handlers():
    """Cleanup helper should remove mitmproxy handlers from all loggers."""
    class FakeMitmHandler(logging.Handler):
        pass

    FakeMitmHandler.__module__ = "mitmproxy.log"

    root_logger = logging.getLogger()
    mitm_logger = logging.getLogger("mitmproxy")
    root_handler = FakeMitmHandler()
    mitm_handler = FakeMitmHandler()
    root_logger.addHandler(root_handler)
    mitm_logger.addHandler(mitm_handler)
    try:
        integration._detach_mitmproxy_handlers()
        assert root_handler not in root_logger.handlers
        assert mitm_handler not in mitm_logger.handlers
    finally:
        if root_handler in root_logger.handlers:
            root_logger.removeHandler(root_handler)
        if mitm_handler in mitm_logger.handlers:
            mitm_logger.removeHandler(mitm_handler)


def test_traffic_collector_records_request_without_response():
    """Collector should persist request-stage data even if no response arrives."""
    captured = []
    collector = integration.TrafficCollector(request_callback=lambda item: captured.append(item))

    request = SimpleNamespace(
        pretty_url="https://api.example.com/v1/home",
        method="GET",
        host="api.example.com",
        path="/v1/home",
        scheme="https",
        timestamp_start=1_700_000_000.0,
        headers={"User-Agent": "ua"},
        content=b"",
        text="",
    )
    server_conn = SimpleNamespace(address=("1.2.3.4", 443))
    flow = SimpleNamespace(request=request, response=None, server_conn=server_conn)

    collector.request(flow)

    assert len(collector.flows) == 1
    assert collector.flows[0]["host"] == "api.example.com"
    assert collector.flows[0]["response_code"] is None
    assert len(captured) == 1


def test_traffic_collector_updates_existing_request_on_response():
    """Response should update previously stored request entry instead of duplicating it."""
    collector = integration.TrafficCollector(request_callback=None)

    request = SimpleNamespace(
        pretty_url="https://api.example.com/v1/home",
        method="GET",
        host="api.example.com",
        path="/v1/home",
        scheme="https",
        timestamp_start=1_700_000_000.0,
        headers={},
        content=b"",
        text="",
    )
    response = SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "application/json"},
        content=b"{\"ok\":1}",
        text='{"ok":1}',
    )
    server_conn = SimpleNamespace(address=("1.2.3.4", 443))
    flow = SimpleNamespace(request=request, response=response, server_conn=server_conn)

    collector.request(flow)
    collector.response(flow)

    assert len(collector.flows) == 1
    assert collector.flows[0]["response_code"] == 200
