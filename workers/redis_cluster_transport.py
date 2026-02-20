"""Custom Kombu transport for Redis Cluster."""
import os
from kombu.transport.redis import Transport as RedisTransport
from kombu.transport.redis import Channel as RedisChannel
from redis.cluster import RedisCluster as RedisClusterClient


class RedisClusterChannel(RedisChannel):
    """Redis Cluster channel that handles MOVED responses."""

    def _create_client(self):
        """Override to create Redis cluster client instead of standard Redis."""
        redis_cluster_nodes = os.getenv("REDIS_CLUSTER_NODES", "")

        if not redis_cluster_nodes:
            # Fallback to standard Redis client
            return super()._create_client()

        # Parse cluster nodes
        nodes_list = []
        for node in redis_cluster_nodes.split(","):
            host, port = node.split(":")
            nodes_list.append({"host": host, "port": int(port)})

        # Get password from connection URL
        password = self.conninfo.password

        # Create Redis cluster client
        return RedisClusterClient(
            startup_nodes=nodes_list,
            password=password if password else None,
            decode_responses=False,
            skip_full_coverage_check=True,
            max_connections=self.max_connections,
        )


class RedisClusterTransport(RedisTransport):
    """Transport for Redis Cluster."""

    Channel = RedisClusterChannel

    default_port = 6379
    driver_type = 'redis'
    driver_name = 'redis-cluster'
