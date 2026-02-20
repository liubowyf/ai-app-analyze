"""Custom Redis cluster backend for Celery."""
from celery.backends.redis import RedisBackend
from celery.exceptions import ImproperlyConfigured
from redis.cluster import RedisCluster as RedisClusterClient
from kombu.transport.redis import Transport
import os


class RedisClusterBackend(RedisBackend):
    """Redis backend that supports Redis Cluster."""

    def _get_client(self, **params):
        """Create Redis cluster client instead of standard Redis client."""
        # Get cluster nodes from environment
        redis_cluster_nodes = os.getenv("REDIS_CLUSTER_NODES", "")
        if not redis_cluster_nodes:
            # Fallback to standard Redis client if no cluster configured
            return super()._get_client(**params)

        # Parse cluster nodes
        nodes_list = []
        for node in redis_cluster_nodes.split(","):
            host, port = node.split(":")
            nodes_list.append({"host": host, "port": int(port)})

        # Extract password from params
        password = params.pop("password", None)

        # Create Redis cluster client
        return RedisClusterClient(
            startup_nodes=nodes_list,
            password=password,
            decode_responses=True,
            skip_full_coverage_check=True,  # Allow partial cluster coverage
            **params
        )
