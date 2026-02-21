"""gRPC protocol parser."""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GRPCParser:
    """Parse gRPC protocol messages."""

    def is_grpc_request(self, headers: Dict) -> bool:
        """
        Check if request is gRPC.

        Args:
            headers: HTTP headers dict

        Returns:
            bool: True if gRPC request
        """
        content_type = headers.get('content-type', '')
        return 'application/grpc' in content_type

    def parse_grpc_message(self, data: bytes) -> Optional[Dict]:
        """
        Parse gRPC message.

        Args:
            data: Raw gRPC message bytes

        Returns:
            Dict with parsed message or None
        """
        try:
            # gRPC format: 5 byte header + payload
            # Header: 1 byte compressed + 4 bytes length
            if len(data) < 5:
                return None

            compressed = data[0]
            message_length = int.from_bytes(data[1:5], byteorder='big')

            if len(data) < 5 + message_length:
                return None

            payload = data[5:5+message_length]

            return {
                'compressed': bool(compressed),
                'length': message_length,
                'payload': payload,
                'payload_hex': payload.hex()
            }

        except Exception as e:
            logger.error(f"Error parsing gRPC message: {e}")
            return None

    def parse_grpc_request(
        self,
        request_headers: Dict,
        request_body: bytes
    ) -> Optional[Dict]:
        """
        Parse gRPC request.

        Args:
            request_headers: Request headers
            request_body: Request body

        Returns:
            Dict with parsed request or None
        """
        if not self.is_grpc_request(request_headers):
            return None

        path = request_headers.get(':path', '')
        message = self.parse_grpc_message(request_body)

        return {
            'type': 'grpc',
            'method': path,
            'message': message
        }
