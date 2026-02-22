"""Runtime behavior tests for traffic monitor resilience."""

from modules.traffic_monitor.monitor import TrafficMonitor


def test_start_retries_next_port_when_default_port_is_busy(monkeypatch):
    """TrafficMonitor.start should retry next proxy port on bind conflict."""
    configured = {}

    class FakeManager:
        def __init__(self):
            self.started_ports = []

        def start_proxy(self, port=8080, request_callback=None):
            self.started_ports.append(port)
            if port == 8080:
                raise OSError("address already in use")

        def stop_proxy(self):
            return None

    def fake_configure_proxy(host, emulator_port, proxy_port):
        configured["host"] = host
        configured["emulator_port"] = emulator_port
        configured["proxy_port"] = proxy_port
        return True

    monkeypatch.setattr(
        "modules.traffic_monitor.mitmproxy_integration.MitmProxyManager",
        FakeManager,
    )
    monkeypatch.setattr(
        "modules.traffic_monitor.mitmproxy_integration.configure_android_proxy",
        fake_configure_proxy,
    )

    monitor = TrafficMonitor(proxy_port=8080)
    monitor.start(emulator_host="10.16.148.66", emulator_port=5555)

    assert monitor.is_running is True
    assert monitor.proxy_port == 8081
    assert monitor._mitmproxy_manager.started_ports == [8080, 8081]
    assert configured["proxy_port"] == 8081


def test_on_request_captured_filters_non_target_foreground_traffic():
    """Only keep requests when target app is currently foreground."""
    monitor = TrafficMonitor(proxy_port=8080)

    class FakeRunner:
        def __init__(self):
            self.calls = 0

        def get_current_package(self, host, port):
            self.calls += 1
            return "com.other.app"

    monitor.set_target_app_context(
        target_package="com.target.app",
        emulator_host="10.16.148.66",
        emulator_port=5558,
        android_runner=FakeRunner(),
    )

    monitor._on_request_captured(
        {
            "url": "https://api.target.com/a",
            "method": "GET",
            "host": "api.target.com",
            "path": "/a",
            "request_time": 1700000000.0,
        }
    )

    assert monitor.get_requests() == []


def test_on_request_captured_filters_connectivity_noise_even_in_target_app():
    """Connectivity-check noise should be dropped to reduce report pollution."""
    monitor = TrafficMonitor(proxy_port=8080)

    class FakeRunner:
        def get_current_package(self, host, port):
            return "com.target.app"

    monitor.set_target_app_context(
        target_package="com.target.app",
        emulator_host="10.16.148.66",
        emulator_port=5558,
        android_runner=FakeRunner(),
    )

    monitor._on_request_captured(
        {
            "url": "http://connectivitycheck.gstatic.com/generate_204",
            "method": "GET",
            "host": "connectivitycheck.gstatic.com",
            "path": "/generate_204",
            "request_time": 1700000000.0,
        }
    )

    monitor._on_request_captured(
        {
            "url": "https://api.target.com/core",
            "method": "POST",
            "host": "api.target.com",
            "path": "/core",
            "request_time": 1700000001.0,
        }
    )

    requests = monitor.get_requests()
    assert len(requests) == 1
    assert requests[0].host == "api.target.com"


def test_on_request_captured_adds_source_and_package_metadata():
    monitor = TrafficMonitor(proxy_port=8080)

    class FakeRunner:
        def get_current_package(self, host, port):
            return "com.target.app"

        def execute_adb_remote(self, host, port, cmd):
            if "pm list packages -U" in cmd:
                return "package:com.target.app uid:10123"
            if "ps -A" in cmd:
                return "u0_a123  999  1234 com.target.app"
            return ""

    monitor.set_target_app_context(
        target_package="com.target.app",
        emulator_host="10.16.148.66",
        emulator_port=5558,
        android_runner=FakeRunner(),
    )

    monitor._on_request_captured(
        {
            "url": "https://api.target.com/v1/home",
            "method": "GET",
            "host": "api.target.com",
            "path": "/v1/home",
            "request_time": 1700000000.0,
            "request_headers": {
                "User-Agent": "okhttp/4.9.3",
                "X-Requested-With": "com.target.app",
            },
        }
    )

    items = monitor.get_requests_as_dict()
    assert len(items) == 1
    assert items[0]["package_name"] == "com.target.app"
    assert items[0]["uid"] == 10123
    assert items[0]["source"] == "okhttp"


def test_get_requests_supports_package_uid_process_filters():
    monitor = TrafficMonitor(proxy_port=8080)

    class FakeRunner:
        def get_current_package(self, host, port):
            return "com.target.app"

        def execute_adb_remote(self, host, port, cmd):
            if "pm list packages -U" in cmd:
                return "package:com.target.app uid:10123"
            if "ps -A" in cmd:
                return "u0_a123  999  1234 com.target.app"
            return ""

    monitor.set_target_app_context(
        target_package="com.target.app",
        emulator_host="10.16.148.66",
        emulator_port=5558,
        android_runner=FakeRunner(),
    )

    monitor._on_request_captured(
        {
            "url": "https://api.target.com/v1/home",
            "method": "GET",
            "host": "api.target.com",
            "path": "/v1/home",
            "request_time": 1700000000.0,
            "request_headers": {"User-Agent": "okhttp/4.9.3"},
        }
    )

    assert len(monitor.get_requests(package_name="com.target.app")) == 1
    assert len(monitor.get_requests(uid=10123)) == 1
    assert len(monitor.get_requests(process_name="com.target.app")) == 1


def test_aggregate_requests_groups_by_host_and_path():
    monitor = TrafficMonitor(proxy_port=8080)

    class FakeRunner:
        def get_current_package(self, host, port):
            return "com.target.app"

        def execute_adb_remote(self, host, port, cmd):
            if "pm list packages -U" in cmd:
                return "package:com.target.app uid:10123"
            if "ps -A" in cmd:
                return "u0_a123  999  1234 com.target.app"
            return ""

    monitor.set_target_app_context(
        target_package="com.target.app",
        emulator_host="10.16.148.66",
        emulator_port=5558,
        android_runner=FakeRunner(),
    )

    flow = {
        "method": "GET",
        "host": "api.target.com",
        "path": "/v1/home",
        "request_time": 1700000000.0,
        "request_headers": {"User-Agent": "okhttp/4.9.3"},
    }
    monitor._on_request_captured({**flow, "url": "https://api.target.com/v1/home"})
    monitor._on_request_captured({**flow, "url": "https://api.target.com/v1/home?from=tab2"})

    grouped = monitor.get_aggregated_requests()
    assert grouped[0]["host"] == "api.target.com"
    assert grouped[0]["path"] == "/v1/home"
    assert grouped[0]["count"] == 2
