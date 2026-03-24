"""数据库连接池与查询缓存模块 (Database Connection Pool & Query Cache)"""
import hashlib
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from common.utils.utils import ChatBILogUtil


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    created_at: float
    ttl: float = 300.0  # 5分钟
    hit_count: int = 0
    sql: str = ""
    ds_id: Optional[int] = None

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl

    @property
    def is_stale(self) -> bool:
        """过期但仍可用作降级数据（2倍TTL内）"""
        age = time.time() - self.created_at
        # 使用 <= 确保 2*TTL 边界值也被视为 stale（可用），
        # 原 < 在精确等于 2*TTL 时会跳过 stale 直接进入"完全过期"分支
        return age > self.ttl and age <= self.ttl * 2


class QueryResultCache:
    """SQL查询结果缓存"""

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "stale_hits": 0, "evictions": 0}
        # 使用独立的 set 存储刷新标记，避免占用缓存容量
        self._refreshing_keys: set = set()

    @staticmethod
    def _make_key(sql: str, ds_id: Optional[int] = None, user_id: Optional[int] = None) -> str:
        """生成缓存键"""
        import re
        # 移除单行注释（-- ...）和多行注释（/* ... */）
        cleaned_sql = re.sub(r'--[^\n]*', '', sql)
        cleaned_sql = re.sub(r'/\*.*?\*/', '', cleaned_sql, flags=re.DOTALL)
        # 限制 SQL 长度，防止超长 SQL 导致正则回溯性能问题
        if len(cleaned_sql) > 10000:
            cleaned_sql = cleaned_sql[:10000]
        normalized_sql = re.sub(r'\s+', ' ', cleaned_sql.strip())
        raw = f"{ds_id or 0}:{user_id or 0}:{normalized_sql}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, sql: str, ds_id: Optional[int] = None, user_id: Optional[int] = None) -> Tuple[Optional[Any], str]:
        """查询缓存"""
        key = self._make_key(sql, ds_id, user_id)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None, "miss"

            if not entry.is_expired:
                entry.hit_count += 1
                self._cache.move_to_end(key)
                self._stats["hits"] += 1
                return entry.data, "hit"

            if entry.is_stale:
                entry.hit_count += 1
                self._stats["stale_hits"] += 1
                # stale 命中时标记需要后台刷新
                # 返回 stale 数据的同时，调用方应触发异步刷新
                return entry.data, "stale"

            # 完全过期，移除
            del self._cache[key]
            self._stats["misses"] += 1
            return None, "miss"

    def put(self, sql: str, data: Any, ds_id: Optional[int] = None,
            ttl: Optional[float] = None, user_id: Optional[int] = None):
        """写入缓存"""
        key = self._make_key(sql, ds_id, user_id)
        with self._lock:
            if key in self._cache:
                del self._cache[key]

            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            self._cache[key] = CacheEntry(
                data=data,
                created_at=time.time(),
                ttl=ttl or self._default_ttl,
                sql=sql,
                ds_id=ds_id,
            )

    def invalidate(self, ds_id: Optional[int] = None):
        """清除指定数据源的缓存"""
        with self._lock:
            if ds_id is None:
                self._cache.clear()
            else:
                keys_to_remove = [
                    k for k, v in self._cache.items()
                    if v.ds_id == ds_id
                ]
                for k in keys_to_remove:
                    del self._cache[k]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"] + self._stats["stale_hits"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_rate": round(hit_rate, 3),
            }

    def mark_refreshing(self, sql: str, ds_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        """使用独立 set 存储刷新标记，不占用缓存容量"""
        key = self._make_key(sql, ds_id, user_id)
        with self._lock:
            if key in self._refreshing_keys:
                return False  # 已有线程在刷新
            self._refreshing_keys.add(key)
            return True

    def clear_refreshing(self, sql: str, ds_id: Optional[int] = None, user_id: Optional[int] = None):
        """清除刷新标记"""
        key = self._make_key(sql, ds_id, user_id)
        with self._lock:
            self._refreshing_keys.discard(key)


# 全局缓存实例
_query_cache = QueryResultCache()


def get_query_cache() -> QueryResultCache:
    """获取全局查询缓存实例"""
    return _query_cache
