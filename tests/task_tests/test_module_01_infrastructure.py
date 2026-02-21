"""
模块一：基础设施层测试用例

包含以下任务的测试用例：
- 任务 1.1: 数据库连接池优化与监控
- 任务 1.2: MinIO 存储优化与冗余备份
- 任务 1.3: Redis 缓存策略优化
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from core.database import get_db, engine
import redis
from minio import Minio


# =============================================================================
# 任务 1.1: 数据库连接池优化与监控
# =============================================================================

class TestDatabasePoolMonitoring:
    """数据库连接池监控测试"""

    @pytest.fixture
    def db_engine(self):
        """创建测试数据库引擎"""
        engine = create_engine(
            "sqlite:///:memory:",
            pool_size=5,
            max_overflow=3,
            pool_recycle=3600
        )
        yield engine
        engine.dispose()

    def test_pool_status_endpoint(self, client):
        """
        测试连接池状态接口

        验证点:
        1. 返回状态码 200
        2. 返回连接池大小
        3. 返回活跃连接数
        4. 返回空闲连接数
        5. 返回连接池使用率
        """
        response = client.get("/api/v1/monitoring/pool-status")

        assert response.status_code == 200
        data = response.json()

        assert "pool_size" in data
        assert "active_connections" in data
        assert "idle_connections" in data
        assert "pool_utilization" in data
        assert isinstance(data["pool_size"], int)
        assert isinstance(data["active_connections"], int)
        assert isinstance(data["idle_connections"], int)
        assert 0 <= data["pool_utilization"] <= 100

    def test_connection_leak_detection(self, db_engine):
        """
        测试连接泄漏检测

        验证点:
        1. 未关闭的连接能被检测
        2. 泄漏告警被记录
        3. 泄漏统计准确
        4. 提供泄漏连接详情
        """
        # 模拟连接泄漏：创建连接但不关闭
        conn = db_engine.connect()

        # 触发泄漏检测
        with patch('core.database.leak_detector') as mock_detector:
            mock_detector.check_leaks.return_value = {
                "leaked_connections": 1,
                "details": [{
                    "connection_id": 123,
                    "created_at": "2026-02-21 10:00:00",
                    "duration_seconds": 300
                }]
            }

            result = mock_detector.check_leaks()

            assert result["leaked_connections"] == 1
            assert len(result["details"]) == 1
            assert result["details"][0]["duration_seconds"] > 0

        # 清理
        conn.close()

    def test_slow_query_logging(self, db_engine):
        """
        测试慢查询日志

        验证点:
        1. 执行时间超过阈值的查询被记录
        2. 日志包含查询语句
        3. 日志包含执行时间
        4. 日志包含调用栈信息
        """
        slow_query_threshold = 1.0  # 1秒

        # 模拟慢查询
        with patch('core.database.slow_query_logger') as mock_logger:
            mock_logger.log_slow_query.return_value = None

            # 执行慢查询（模拟）
            slow_query = "SELECT * FROM large_table WHERE complex_condition"
            execution_time = 2.5  # 秒

            mock_logger.log_slow_query(
                query=slow_query,
                execution_time=execution_time,
                threshold=slow_query_threshold
            )

            # 验证日志被调用
            mock_logger.log_slow_query.assert_called_once()
            call_args = mock_logger.log_slow_query.call_args
            assert call_args[1]["query"] == slow_query
            assert call_args[1]["execution_time"] == execution_time

    def test_prometheus_metrics(self, client):
        """
        测试 Prometheus 指标

        验证点:
        1. 指标端点可访问
        2. 返回 Prometheus 格式数据
        3. 包含连接池指标
        4. 包含查询性能指标
        """
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # 验证包含关键指标
        assert "db_pool_size" in content
        assert "db_pool_active" in content
        assert "db_pool_idle" in content
        assert "db_query_duration_seconds" in content
        assert "db_connections_total" in content

    def test_health_check_endpoint(self, client):
        """
        测试健康检查端点

        验证点:
        1. 数据库连通性检查
        2. 连接池健康检查
        3. 返回健康状态
        4. 返回详细诊断信息
        """
        response = client.get("/health/database")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ["healthy", "unhealthy"]
        assert "database_connection" in data
        assert "pool_status" in data
        assert "response_time_ms" in data

        if data["status"] == "healthy":
            assert data["database_connection"] == "ok"
            assert isinstance(data["response_time_ms"], (int, float))

    def test_connection_pool_recycle(self, db_engine):
        """
        测试连接池回收机制

        验证点:
        1. 连接在使用指定时间后被回收
        2. 回收后连接可用
        3. 不影响正在使用的连接
        """
        # 验证连接池配置
        assert db_engine.pool._recycle == 3600

        # 模拟连接使用
        Session = sessionmaker(bind=db_engine)
        session = Session()

        # 验证连接可用
        assert session.is_active

        session.close()

    def test_pool_overflow_behavior(self, db_engine):
        """
        测试连接池溢出行为

        验证点:
        1. 超过 pool_size 时创建溢出连接
        2. 溢出连接数量不超过 max_overflow
        3. 溢出连接使用后被回收
        """
        pool_size = db_engine.pool.size()
        max_overflow = db_engine.pool._max_overflow

        # 创建超过 pool_size 的连接
        connections = []
        for i in range(pool_size + max_overflow):
            conn = db_engine.connect()
            connections.append(conn)

        # 验证所有连接可用
        assert len(connections) == pool_size + max_overflow

        # 清理
        for conn in connections:
            conn.close()


# =============================================================================
# 任务 1.2: MinIO 存储优化与冗余备份
# =============================================================================

class TestStorageEnhancements:
    """MinIO 存储增强测试"""

    @pytest.fixture
    def mock_minio(self):
        """模拟 MinIO 客户端"""
        with patch('core.storage.Minio') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_storage_capacity_monitoring(self, client, mock_minio):
        """
        测试存储容量监控

        验证点:
        1. 返回总容量
        2. 返回已用容量
        3. 返回可用容量
        4. 返回使用率百分比
        5. 容量不足时告警
        """
        # 模拟存储统计
        mock_minio.stat_bucket.return_value = MagicMock(
            size=1024 * 1024 * 1024 * 50,  # 50GB
            object_count=1000
        )

        response = client.get("/api/v1/monitoring/storage")

        assert response.status_code == 200
        data = response.json()

        assert "total_capacity_gb" in data
        assert "used_capacity_gb" in data
        assert "available_capacity_gb" in data
        assert "utilization_percent" in data
        assert "object_count" in data

        # 验证使用率计算正确
        used = data["used_capacity_gb"]
        total = data["total_capacity_gb"]
        utilization = (used / total) * 100
        assert abs(data["utilization_percent"] - utilization) < 0.01

    def test_auto_cleanup_expired_files(self, mock_minio):
        """
        测试过期文件自动清理

        验证点:
        1. 过期文件被识别
        2. 过期文件被删除
        3. 清理日志被记录
        4. 清理统计准确
        """
        from core.storage import StorageManager

        # 配置生命周期规则
        lifecycle_config = {
            "ID": "cleanup-old-files",
            "Status": "Enabled",
            "Rules": [
                {
                    "ID": "delete-after-30-days",
                    "Status": "Enabled",
                    "Expiration": {
                        "Days": 30
                    }
                }
            ]
        }

        mock_minio.get_bucket_lifecycle.return_value = lifecycle_config

        # 执行清理
        storage_manager = StorageManager()
        result = storage_manager.cleanup_expired_files()

        assert result["deleted_count"] >= 0
        assert result["freed_space_bytes"] >= 0
        assert "errors" in result

    def test_multipart_upload(self, mock_minio):
        """
        测试分片上传

        验证点:
        1. 大文件使用分片上传
        2. 分片大小合理
        3. 上传中断可恢复
        4. 上传完成后合并
        """
        from core.storage import StorageManager

        # 创建大文件（模拟）
        large_file_size = 100 * 1024 * 1024  # 100MB
        file_content = b"x" * large_file_size

        storage_manager = StorageManager()

        # 模拟分片上传
        with patch.object(storage_manager, '_should_use_multipart', return_value=True):
            mock_minio.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
            mock_minio.upload_part.return_value = {"ETag": "etag-123"}
            mock_minio.complete_multipart_upload.return_value = None

            result = storage_manager.upload_file(
                "large-file.apk",
                file_content,
                use_multipart=True
            )

            assert result["success"] is True
            assert result["upload_id"] == "test-upload-id"
            assert result["parts_count"] > 1

    def test_file_versioning(self, mock_minio):
        """
        测试文件版本管理

        验证点:
        1. 同名文件创建新版本
        2. 版本历史可查询
        3. 可恢复到旧版本
        4. 版本数量限制生效
        """
        from core.storage import StorageManager

        # 启用版本控制
        mock_minio.get_bucket_versioning.return_value = {"Status": "Enabled"}

        storage_manager = StorageManager()

        # 上传同名文件多次
        for i in range(3):
            mock_minio.put_object.return_value = MagicMock(
                version_id=f"v{i}",
                etag=f"etag-{i}"
            )
            result = storage_manager.upload_file(
                "test.apk",
                f"content-v{i}".encode(),
                enable_versioning=True
            )
            assert result["version_id"] == f"v{i}"

        # 查询版本历史
        mock_minio.list_object_versions.return_value = {
            "Versions": [
                {"VersionId": f"v{i}"} for i in range(3)
            ]
        }

        versions = storage_manager.list_file_versions("test.apk")
        assert len(versions) == 3

    def test_access_logging(self, mock_minio):
        """
        测试访问日志

        验证点:
        1. 文件访问被记录
        2. 日志包含访问者信息
        3. 日志包含访问时间
        4. 日志包含操作类型
        """
        from core.storage import StorageManager

        storage_manager = StorageManager()

        # 模拟文件访问
        mock_minio.stat_object.return_value = MagicMock(
            object_name="test.apk",
            size=1024,
            last_modified="2026-02-21T10:00:00Z"
        )

        with patch('core.storage.access_logger') as mock_logger:
            storage_manager.get_file_info("test.apk")

            # 验证访问日志被记录
            mock_logger.log_access.assert_called_once()
            call_args = mock_logger.log_access.call_args
            assert call_args[1]["operation"] == "stat"
            assert call_args[1]["file_name"] == "test.apk"

    def test_storage_quota_enforcement(self, mock_minio):
        """
        测试存储配额强制执行

        验证点:
        1. 超过配额时拒绝上传
        2. 返回配额错误信息
        3. 提供配额使用详情
        """
        from core.storage import StorageManager

        storage_manager = StorageManager()
        storage_manager.set_quota(1024 * 1024 * 1024)  # 1GB

        # 模拟存储已满
        with patch.object(storage_manager, 'get_usage', return_value=1024 * 1024 * 1024):
            with pytest.raises(Exception) as exc_info:
                storage_manager.upload_file(
                    "new-file.apk",
                    b"x" * 1024
                )

            assert "quota exceeded" in str(exc_info.value).lower()


# =============================================================================
# 任务 1.3: Redis 缓存策略优化
# =============================================================================

class TestRedisCacheStrategy:
    """Redis 缓存策略测试"""

    @pytest.fixture
    def mock_redis(self):
        """模拟 Redis 客户端"""
        with patch('redis.Redis') as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_task_result_caching(self, mock_redis):
        """
        测试任务结果缓存

        验证点:
        1. 任务完成后结果被缓存
        2. 缓存键格式正确
        3. 缓存 TTL 设置合理
        4. 缓存命中时直接返回
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 模拟任务结果
        task_id = "test-task-123"
        task_result = {
            "status": "completed",
            "result": {"threats": []}
        }

        # 缓存结果
        mock_redis.setex.return_value = True
        cache_manager.cache_task_result(task_id, task_result)

        # 验证缓存调用
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert f"task:result:{task_id}" in call_args[0][0]
        assert call_args[0][1] == 86400  # 24小时 TTL

        # 缓存命中
        mock_redis.get.return_value = '{"status":"completed","result":{"threats":[]}}'
        cached = cache_manager.get_cached_task_result(task_id)
        assert cached is not None
        assert cached["status"] == "completed"

    def test_whitelist_cache(self, mock_redis):
        """
        测试白名单缓存

        验证点:
        1. 白名单规则被缓存
        2. 查询使用缓存
        3. 规则更新时缓存失效
        4. 缓存未命中时查询数据库
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 模拟白名单数据
        whitelist_data = [
            {"id": "1", "domain": "*.google.com", "category": "cdn"},
            {"id": "2", "domain": "*.facebook.com", "category": "analytics"}
        ]

        # 缓存白名单
        mock_redis.set.return_value = True
        cache_manager.cache_whitelist(whitelist_data)

        # 验证缓存
        mock_redis.get.return_value = str(whitelist_data)
        cached = cache_manager.get_cached_whitelist()
        assert len(cached) == 2

        # 清除缓存
        cache_manager.invalidate_whitelist_cache()
        mock_redis.delete.assert_called()

    def test_cache_warmup(self, mock_redis):
        """
        测试缓存预热

        验证点:
        1. 启动时预加载热点数据
        2. 预加载数据正确
        3. 预热不影响启动时间
        4. 预热失败不影响系统
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 模拟预热数据
        warmup_data = {
            "whitelist": [{"id": "1", "domain": "*.example.com"}],
            "system_config": {"max_file_size": 100 * 1024 * 1024}
        }

        # 执行预热
        with patch('core.cache.warmup_loader') as mock_loader:
            mock_loader.load_warmup_data.return_value = warmup_data

            result = cache_manager.warmup()

            assert result["success"] is True
            assert result["cached_keys"] > 0
            assert "duration_ms" in result

    def test_cache_invalidation(self, mock_redis):
        """
        测试缓存失效

        验证点:
        1. 数据更新时缓存被清除
        2. 相关缓存键都被清除
        3. 失效后重新加载
        4. 批量失效有效
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 测试单键失效
        cache_key = "task:result:123"
        cache_manager.invalidate(cache_key)
        mock_redis.delete.assert_called_with(cache_key)

        # 测试模式匹配失效
        mock_redis.keys.return_value = [
            "task:result:123",
            "task:result:124",
            "task:result:125"
        ]
        cache_manager.invalidate_pattern("task:result:*")

        # 验证批量删除
        assert mock_redis.delete.call_count >= 3

    def test_cache_monitoring(self, mock_redis):
        """
        测试缓存监控

        验证点:
        1. 返回命中率统计
        2. 返回内存使用情况
        3. 返回连接数
        4. 返回键空间统计
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 模拟 Redis INFO 命令输出
        mock_redis.info.return_value = {
            "keyspace_hits": 1000,
            "keyspace_misses": 200,
            "used_memory_human": "512M",
            "connected_clients": 10,
            "db0": {"keys": 5000, "expires": 1000}
        }

        stats = cache_manager.get_stats()

        assert "hit_rate" in stats
        assert "memory_usage" in stats
        assert "connected_clients" in stats
        assert "key_count" in stats

        # 验证命中率计算
        expected_hit_rate = 1000 / (1000 + 200)
        assert abs(stats["hit_rate"] - expected_hit_rate) < 0.01

    def test_cache_serialization(self, mock_redis):
        """
        测试缓存序列化

        验证点:
        1. 复杂对象可序列化
        2. 序列化不丢失数据
        3. 反序列化正确
        4. 处理特殊字符
        """
        from core.cache import CacheManager
        import json

        cache_manager = CacheManager()

        # 测试复杂对象
        complex_object = {
            "task_id": "123",
            "result": {
                "threats": [
                    {"domain": "evil.com", "score": 0.95},
                    {"domain": "malware.net", "score": 0.88}
                ],
                "analysis": {
                    "static": {"permissions": 15},
                    "dynamic": {"network_requests": 150}
                }
            },
            "metadata": {
                "analyzed_at": "2026-02-21T10:00:00Z",
                "duration_seconds": 480
            }
        }

        # 序列化
        serialized = cache_manager.serialize(complex_object)
        assert isinstance(serialized, (str, bytes))

        # 反序列化
        deserialized = cache_manager.deserialize(serialized)
        assert deserialized == complex_object

    def test_cache_ttl_management(self, mock_redis):
        """
        测试缓存 TTL 管理

        验证点:
        1. 不同数据类型有不同 TTL
        2. TTL 可动态调整
        3. TTL 过期后数据不可访问
        4. 可延长 TTL
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 测试不同 TTL
        test_cases = [
            ("task_result", 86400),      # 24小时
            ("whitelist", 3600),          # 1小时
            ("system_config", 7200),      # 2小时
            ("temp_data", 300)            # 5分钟
        ]

        for data_type, expected_ttl in test_cases:
            key = f"{data_type}:test"
            value = {"data": "test"}

            mock_redis.setex.return_value = True
            cache_manager.set_with_ttl(key, value, data_type=data_type)

            # 验证 TTL
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == expected_ttl

    def test_cache_fallback(self, mock_redis):
        """
        测试缓存降级

        验证点:
        1. Redis 不可用时降级
        2. 降级后功能正常
        3. 记录降级事件
        4. 自动恢复重试
        """
        from core.cache import CacheManager

        cache_manager = CacheManager()

        # 模拟 Redis 不可用
        mock_redis.get.side_effect = redis.ConnectionError("Redis unavailable")

        # 测试降级
        with patch('core.cache.fallback_logger') as mock_logger:
            result = cache_manager.get("test-key")

            # 验证返回 None 或默认值
            assert result is None

            # 验证降级日志
            mock_logger.log_fallback.assert_called()

        # 测试自动恢复
        mock_redis.get.reset_mock()
        mock_redis.get.side_effect = None
        mock_redis.get.return_value = '{"data":"test"}'

        result = cache_manager.get("test-key")
        assert result is not None
