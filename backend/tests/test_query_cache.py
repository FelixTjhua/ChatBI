"""数据库查询缓存测试"""
import time
import pytest
from apps.datasource.db_connection_pool import (
    QueryResultCache, CacheEntry, get_query_cache,
)


class TestCacheEntry:
    """测试缓存条目"""

    def test_not_expired(self):
        entry = CacheEntry(data="test", created_at=time.time(), ttl=300)
        assert entry.is_expired is False

    def test_expired(self):
        entry = CacheEntry(data="test", created_at=time.time() - 400, ttl=300)
        assert entry.is_expired is True

    def test_stale(self):
        entry = CacheEntry(data="test", created_at=time.time() - 400, ttl=300)
        assert entry.is_stale is True

    def test_fully_expired(self):
        entry = CacheEntry(data="test", created_at=time.time() - 700, ttl=300)
        assert entry.is_expired is True
        assert entry.is_stale is False


class TestQueryResultCache:
    """测试查询结果缓存"""

    def test_put_and_get(self):
        cache = QueryResultCache(max_size=10)
        cache.put("SELECT 1", {"result": 1}, ds_id=1)
        data, status = cache.get("SELECT 1", ds_id=1)
        assert data == {"result": 1}
        assert status == "hit"

    def test_cache_miss(self):
        cache = QueryResultCache(max_size=10)
        data, status = cache.get("SELECT 1", ds_id=1)
        assert data is None
        assert status == "miss"

    def test_lru_eviction(self):
        cache = QueryResultCache(max_size=3)
        cache.put("SQL1", "data1", ds_id=1)
        cache.put("SQL2", "data2", ds_id=1)
        cache.put("SQL3", "data3", ds_id=1)
        # Access SQL1 to make it recently used
        cache.get("SQL1", ds_id=1)
        # Add SQL4, should evict SQL2 (least recently used)
        cache.put("SQL4", "data4", ds_id=1)
        data, status = cache.get("SQL2", ds_id=1)
        assert status == "miss"
        data, status = cache.get("SQL1", ds_id=1)
        assert status == "hit"

    def test_invalidate_by_ds(self):
        cache = QueryResultCache(max_size=10)
        cache.put("SQL1", "data1", ds_id=1)
        cache.put("SQL2", "data2", ds_id=2)
        cache.invalidate(ds_id=1)
        data1, _ = cache.get("SQL1", ds_id=1)
        data2, _ = cache.get("SQL2", ds_id=2)
        assert data1 is None
        assert data2 == "data2"

    def test_invalidate_all(self):
        cache = QueryResultCache(max_size=10)
        cache.put("SQL1", "data1", ds_id=1)
        cache.put("SQL2", "data2", ds_id=2)
        cache.invalidate()
        assert cache.get_stats()["size"] == 0

    def test_stats(self):
        cache = QueryResultCache(max_size=10)
        cache.put("SQL1", "data1", ds_id=1)
        cache.get("SQL1", ds_id=1)  # hit
        cache.get("SQL2", ds_id=1)  # miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_global_cache_singleton(self):
        cache1 = get_query_cache()
        cache2 = get_query_cache()
        assert cache1 is cache2
