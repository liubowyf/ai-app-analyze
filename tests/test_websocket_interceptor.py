"""Test WebSocket interceptor."""
import pytest
from modules.traffic_monitor.websocket_interceptor import WebSocketInterceptor


class TestWebSocketInterceptor:
    """Test WebSocket interceptor."""

    def test_interceptor_initialization(self):
        """Test interceptor initialization."""
        interceptor = WebSocketInterceptor()

        assert interceptor.messages == []

    def test_interceptor_stores_messages(self):
        """Test that interceptor can store messages."""
        interceptor = WebSocketInterceptor()

        # This is a simplified test - real testing would need mock mitmproxy flows
        interceptor.messages.append({
            'type': 'websocket',
            'direction': 'send',
            'payload': b'test message'
        })

        messages = interceptor.get_messages()
        assert len(messages) == 1
        assert messages[0]['type'] == 'websocket'
        assert messages[0]['direction'] == 'send'
