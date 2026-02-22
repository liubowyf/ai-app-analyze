"""MitmProxy integration for network traffic capture."""
import asyncio
import logging
import os
import socket
import threading
from typing import Optional, Callable, Dict, Any
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.http import HTTPFlow

logger = logging.getLogger(__name__)


def _detach_mitmproxy_handlers() -> None:
    """Remove mitmproxy logging handlers that may hold closed event loops."""
    logger_names = ["", "mitmproxy"] + list(logging.root.manager.loggerDict.keys())
    for name in logger_names:
        target = logging.getLogger(name)
        for handler in list(target.handlers):
            module_name = type(handler).__module__
            if module_name.startswith("mitmproxy"):
                target.removeHandler(handler)


class TrafficCollector:
    """MitmProxy addon to collect HTTP traffic."""

    def __init__(self, request_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Initialize traffic collector.

        Args:
            request_callback: Optional callback function for each request
        """
        self.request_callback = request_callback
        self.flows: list = []
        self._flow_index: Dict[int, int] = {}

    @staticmethod
    def _build_flow_data(flow: HTTPFlow, include_response: bool) -> Dict[str, Any]:
        """Build normalized request/response payload from mitmproxy flow."""
        return {
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "host": flow.request.host,
            "path": flow.request.path,
            "ip": flow.server_conn.address[0] if flow.server_conn.address else None,
            "port": flow.server_conn.address[1] if flow.server_conn.address else 80,
            "scheme": flow.request.scheme,
            "request_time": flow.request.timestamp_start,
            "response_code": flow.response.status_code if include_response and flow.response else None,
            "content_type": flow.response.headers.get("Content-Type", "") if include_response and flow.response else None,
            "request_headers": dict(flow.request.headers),
            "response_headers": dict(flow.response.headers) if include_response and flow.response else {},
            "request_body": flow.request.text if flow.request.content else None,
            "response_body": flow.response.text if include_response and flow.response and flow.response.content else None,
        }

    def request(self, flow: HTTPFlow) -> None:
        """Capture request at request stage to avoid losing no-response traffic."""
        try:
            request_data = self._build_flow_data(flow, include_response=False)
            self.flows.append(request_data)
            self._flow_index[id(flow)] = len(self.flows) - 1

            if self.request_callback:
                self.request_callback(request_data)

            logger.debug("Captured request: %s %s", request_data["method"], request_data["host"])
        except Exception as e:
            logger.error(f"Failed to process request flow: {e}")

    def response(self, flow: HTTPFlow) -> None:
        """
        Called when a response is received.

        Args:
            flow: HTTP flow object
        """
        try:
            flow_id = id(flow)
            response_data = self._build_flow_data(flow, include_response=True)

            if flow_id in self._flow_index:
                idx = self._flow_index[flow_id]
                if 0 <= idx < len(self.flows):
                    self.flows[idx].update({
                        "response_code": response_data["response_code"],
                        "content_type": response_data["content_type"],
                        "response_headers": response_data["response_headers"],
                        "response_body": response_data["response_body"],
                    })
                self._flow_index.pop(flow_id, None)
            else:
                self.flows.append(response_data)
                if self.request_callback:
                    self.request_callback(response_data)

            logger.debug(f"Captured response: {response_data['method']} {response_data['host']}{response_data['path']}")

        except Exception as e:
            logger.error(f"Failed to process flow: {e}")


class MitmProxyManager:
    """Manages mitmproxy instance for traffic capture."""

    def __init__(self):
        """Initialize mitmproxy manager."""
        self.master: Optional[DumpMaster] = None
        self.collector: Optional[TrafficCollector] = None
        self.proxy_port: int = 8080
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start_proxy(self, port: int = 8080, request_callback: Optional[Callable] = None) -> None:
        """
        Start mitmproxy server.

        Args:
            port: Port to listen on
            request_callback: Callback function for each request
        """
        try:
            self.proxy_port = port
            self.collector = TrafficCollector(request_callback)

            # Configure mitmproxy options
            opts = options.Options(
                listen_host="0.0.0.0",
                listen_port=port,
                http2=True,
                ssl_insecure=True,  # Allow self-signed certificates
            )

            # Mitmproxy master requires an event loop at construction time.
            self._loop = asyncio.new_event_loop()

            # Create master with addon
            self.master = DumpMaster(
                opts,
                loop=self._loop,
                with_termlog=False,
                with_dumper=False,
            )
            self.master.addons.add(self.collector)

            self._running = True
            logger.info(f"Starting mitmproxy on port {port}")

            # Run in background thread with dedicated event loop
            self._thread = threading.Thread(
                target=self._run_proxy_loop,
                name=f"mitmproxy-{port}",
                daemon=True,
            )
            self._thread.start()

        except Exception as e:
            self._running = False
            try:
                if self.master:
                    self.master.shutdown()
            except Exception:
                pass
            _detach_mitmproxy_handlers()
            logger.error(f"Failed to start mitmproxy: {e}")
            raise

    def _run_proxy_loop(self) -> None:
        """Run proxy coroutine in a dedicated thread loop."""
        try:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.master.run())
        except Exception as e:
            logger.error(f"Proxy server error: {e}")
        finally:
            self._running = False
            if self._loop and not self._loop.is_closed():
                self._loop.close()
            _detach_mitmproxy_handlers()

    def stop_proxy(self) -> None:
        """Stop mitmproxy server."""
        try:
            if self.master:
                logger.info("Stopping mitmproxy")
                try:
                    if self._loop and self._loop.is_running():
                        self._loop.call_soon_threadsafe(self.master.shutdown)
                    else:
                        self.master.shutdown()
                except RuntimeError as exc:
                    # If the loop already closed in background thread, shutdown is effectively complete.
                    if "event loop is closed" in str(exc).lower():
                        logger.debug("Mitmproxy loop already closed during shutdown")
                    else:
                        raise
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=5)
        except RuntimeError as exc:
            if "event loop is closed" in str(exc).lower():
                logger.debug("Mitmproxy stop skipped because loop already closed")
            else:
                logger.warning("Mitmproxy stop encountered runtime error: %s", exc)
        except Exception as exc:
            logger.warning("Mitmproxy stop encountered error: %s", exc)
        finally:
            self._running = False
            self.master = None
            self.collector = None
            self._loop = None
            self._thread = None
            _detach_mitmproxy_handlers()
            logger.info("Mitmproxy stopped")

    def get_flows(self) -> list:
        """
        Get all captured flows.

        Returns:
            List of flow data dictionaries
        """
        if self.collector:
            return self.collector.flows
        return []

    def clear_flows(self) -> None:
        """Clear all captured flows."""
        if self.collector:
            self.collector.flows.clear()
            logger.info("Cleared all captured flows")

    @property
    def is_running(self) -> bool:
        """Check if proxy is running."""
        return self._running


def _resolve_proxy_host(emulator_host: str) -> str:
    """
    Resolve host IP that remote emulator should use to reach this proxy.

    Priority:
    1) Environment override: MITMPROXY_HOST / TRAFFIC_PROXY_HOST
    2) Auto-detect outbound interface IP towards emulator host
    3) Fallback: 127.0.0.1
    """
    configured = os.getenv("MITMPROXY_HOST") or os.getenv("TRAFFIC_PROXY_HOST")
    if configured:
        return configured

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((emulator_host, 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def configure_android_proxy(emulator_host: str, emulator_port: int, proxy_port: int) -> bool:
    """
    Configure Android emulator to use mitmproxy.

    Args:
        emulator_host: Emulator host IP
        emulator_port: Emulator ADB port
        proxy_port: Mitmproxy port

    Returns:
        True if successful
    """
    try:
        from modules.android_runner import AndroidRunner

        runner = AndroidRunner()

        # Prefer adb reverse so remote emulator can always reach local proxy as 127.0.0.1.
        proxy_host: Optional[str] = None
        reverse_output = runner.execute_adb_remote(
            emulator_host, emulator_port,
            f"reverse tcp:{proxy_port} tcp:{proxy_port}"
        )
        if "error" not in (reverse_output or "").lower():
            proxy_host = "127.0.0.1"
            logger.info(
                "Configured adb reverse for %s:%s tcp:%s -> local tcp:%s",
                emulator_host,
                emulator_port,
                proxy_port,
                proxy_port,
            )

        # Fallback to network host IP when reverse is unavailable.
        if not proxy_host:
            proxy_host = _resolve_proxy_host(emulator_host)

        # Set proxy
        result = runner.execute_adb_remote(
            emulator_host, emulator_port,
            f"shell settings put global http_proxy {proxy_host}:{proxy_port}"
        )

        # Verify
        proxy = runner.execute_adb_remote(
            emulator_host, emulator_port,
            "shell settings get global http_proxy"
        ).strip()

        success = f"{proxy_host}:{proxy_port}" in proxy

        if success:
            logger.info(f"Configured proxy for {emulator_host}:{emulator_port} -> {proxy_host}:{proxy_port}")
        else:
            logger.error(f"Failed to configure proxy: {proxy}")

        return success

    except Exception as e:
        logger.error(f"Failed to configure Android proxy: {e}")
        return False


def install_mitmproxy_cert(emulator_host: str, emulator_port: int) -> bool:
    """
    Install mitmproxy certificate on Android emulator for HTTPS interception.

    Args:
        emulator_host: Emulator host IP
        emulator_port: Emulator ADB port

    Returns:
        True if successful
    """
    try:
        import os
        import tempfile
        from modules.android_runner import AndroidRunner

        runner = AndroidRunner()

        # Generate certificate if not exists
        cert_path = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.cer")

        if not os.path.exists(cert_path):
            logger.error("Mitmproxy certificate not found. Please start mitmproxy first to generate certificates.")
            return False

        # Push certificate to emulator
        with tempfile.NamedTemporaryFile(suffix=".cer", delete=False) as tmp:
            tmp_cert_path = tmp.name

        # Copy cert to temp location
        import shutil
        shutil.copy(cert_path, tmp_cert_path)

        # Push to emulator
        runner.execute_adb_remote(
            emulator_host, emulator_port,
            f"push {tmp_cert_path} /sdcard/Download/mitmproxy-cert.cer"
        )

        logger.info(f"Certificate pushed to {emulator_host}:{emulator_port}")
        logger.info("Please manually install the certificate from Settings > Security > Install from storage")

        # Cleanup
        os.unlink(tmp_cert_path)

        return True

    except Exception as e:
        logger.error(f"Failed to install certificate: {e}")
        return False
