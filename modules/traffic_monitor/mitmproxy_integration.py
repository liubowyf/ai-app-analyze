"""MitmProxy integration for network traffic capture."""
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from mitmproxy import proxy, options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.http import HTTPFlow

logger = logging.getLogger(__name__)


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

    def response(self, flow: HTTPFlow) -> None:
        """
        Called when a response is received.

        Args:
            flow: HTTP flow object
        """
        try:
            # Extract request/response data
            request_data = {
                "url": flow.request.pretty_url,
                "method": flow.request.method,
                "host": flow.request.host,
                "path": flow.request.path,
                "ip": flow.server_conn.address[0] if flow.server_conn.address else None,
                "port": flow.server_conn.address[1] if flow.server_conn.address else 80,
                "scheme": flow.request.scheme,
                "request_time": flow.request.timestamp_start,
                "response_code": flow.response.status_code if flow.response else None,
                "content_type": flow.response.headers.get("Content-Type", "") if flow.response else None,
                "request_headers": dict(flow.request.headers),
                "response_headers": dict(flow.response.headers) if flow.response else {},
                "request_body": flow.request.text if flow.request.content else None,
                "response_body": flow.response.text if flow.response and flow.response.content else None,
            }

            # Store flow
            self.flows.append(request_data)

            # Call callback if provided
            if self.request_callback:
                self.request_callback(request_data)

            logger.debug(f"Captured: {request_data['method']} {request_data['host']}{request_data['path']}")

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

    async def start_proxy(self, port: int = 8080, request_callback: Optional[Callable] = None) -> None:
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

            # Create proxy configuration
            pconf = proxy.config.ProxyConfig(opts)

            # Create master with addon
            self.master = DumpMaster(opts)
            self.master.addons.add(self.collector)

            self._running = True
            logger.info(f"Starting mitmproxy on port {port}")

            # Run in background
            asyncio.create_task(self._run_proxy())

        except Exception as e:
            logger.error(f"Failed to start mitmproxy: {e}")
            raise

    async def _run_proxy(self) -> None:
        """Run the proxy server."""
        try:
            await self.master.run()
        except Exception as e:
            logger.error(f"Proxy server error: {e}")
            self._running = False

    async def stop_proxy(self) -> None:
        """Stop mitmproxy server."""
        if self.master:
            logger.info("Stopping mitmproxy")
            self.master.shutdown()
            self._running = False
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

        # Get host IP that Android can reach
        # Assuming the proxy runs on the same host as the emulator
        proxy_host = "10.16.150.4"  # Should be configurable

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
