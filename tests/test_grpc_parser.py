"""Test gRPC parser."""
import pytest
from modules.traffic_monitor.grpc_parser import GRPCParser


class TestGRPCParser:
    """Test gRPC parser."""

    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = GRPCParser()
        assert parser is not None

    def test_is_grpc_request_true(self):
        """Test gRPC detection with gRPC content type."""
        parser = GRPCParser()

        headers = {'content-type': 'application/grpc'}
        result = parser.is_grpc_request(headers)

        assert result is True

    def test_is_grpc_request_false(self):
        """Test gRPC detection with regular content type."""
        parser = GRPCParser()

        headers = {'content-type': 'application/json'}
        result = parser.is_grpc_request(headers)

        assert result is False

    def test_parse_grpc_message(self):
        """Test parsing gRPC message."""
        parser = GRPCParser()

        # gRPC message format: 1 byte compressed flag + 4 bytes length + payload
        data = b'\x00\x00\x00\x00\x05hello'

        result = parser.parse_grpc_message(data)

        assert result is not None
        assert result['compressed'] is False
        assert result['length'] == 5
        assert result['payload'] == b'hello'
