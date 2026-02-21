"""WebSocket message interceptor."""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class WebSocketInterceptor:
    """Intercept and log WebSocket messages."""

    def __init__(self):
        """Initialize interceptor."""
        self.messages: List[Dict] = []

    def websocket_message(self, flow):
        """
        Handle WebSocket message from mitmproxy.

        Args:
            flow: mitmproxy flow object
        """
        try:
            message = flow.websocket.messages[-1]

            message_data = {
                'timestamp': message.timestamp,
                'type': 'websocket',
                'direction': 'send' if message.from_client else 'receive',
                'payload': message.content,
                'payload_length': len(message.content),
                'opcode': message.type,
            }

            self.messages.append(message_data)

            logger.debug(
                f"WebSocket message: {message_data['direction']}, "
                f"length={message_data['payload_length']}"
            )
        except Exception as e:
            logger.error(f"Error intercepting WebSocket message: {e}")

    def get_messages(self) -> List[Dict]:
        """
        Get all intercepted messages.

        Returns:
            List of message dictionaries
        """
        return self.messages

    def clear_messages(self):
        """Clear all stored messages."""
        self.messages.clear()
