"""Redis cluster connection pool for Celery/Kombu."""
import os
from redis.cluster import RedisCluster as RedisClusterClient
from redis.connection import ConnectionPool


def create_redis_cluster_pool():
    """Create a Redis cluster connection pool."""
    redis_cluster_nodes = os.getenv("REDIS_CLUSTER_NODES", "")
    password = os.getenv("REDIS_PASSWORD", "")

    if not redis_cluster_nodes:
        raise ValueError("REDIS_CLUSTER_NODES not configured")

    # Parse cluster nodes
    nodes_list = []
    for node in redis_cluster_nodes.split(","):
        host, port = node.split(":")
        nodes_list.append({"host": host, "port": int(port)})

    # Create Redis cluster client
    client = RedisClusterClient(
        startup_nodes=nodes_list,
        password=password if password else None,
        decode_responses=False,
        skip_full_coverage_check=True,
    )

    return client


# Singleton cluster client
_cluster_client = None


def get_cluster_client():
    """Get or create singleton Redis cluster client."""
    global _cluster_client
    if _cluster_client is None:
        _cluster_client = create_redis_cluster_pool()
    return _cluster_client
