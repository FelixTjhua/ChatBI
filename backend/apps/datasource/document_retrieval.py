"""文档知识库语义检索模块（重构版）"""
import threading
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from common.utils.utils import ChatBILogUtil


# 使用线程安全的手动缓存替代 @lru_cache
class _EmbeddingQueryCache:
    """线程安全的查询向量缓存，支持主动失效和 TTL 过期"""
    def __init__(self, maxsize: int = 32, ttl: int = 3600):
        from collections import OrderedDict
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}  # query -> insert_time
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()
        # per-query 锁：防止同一 query 被多个线程并发计算
        self._query_locks: dict = {}  # query -> threading.Lock()

    def _is_expired(self, query: str) -> bool:
        """检查缓存条目是否已过期"""
        import time
        ts = self._timestamps.get(query, 0)
        return (time.time() - ts) > self._ttl

    def get_or_compute(self, query: str) -> list:
        # 快路径：缓存命中且未过期
        with self._lock:
            if query in self._cache and not self._is_expired(query):
                self._cache.move_to_end(query)
                return list(self._cache[query])
            # 过期则移除
            if query in self._cache:
                del self._cache[query]
                self._timestamps.pop(query, None)
            # 获取或创建该 query 的专属锁
            if query not in self._query_locks:
                self._query_locks[query] = threading.Lock()
            q_lock = self._query_locks[query]

        # 持有 per-query 锁，保证同一 query 只有一个线程计算
        with q_lock:
            # double-check：可能在等锁期间已被其他线程填充
            with self._lock:
                if query in self._cache and not self._is_expired(query):
                    self._cache.move_to_end(query)
                    return list(self._cache[query])

            # 使用 try/finally 确保异常时也清理 per-query 锁
            # 导致字典无限增长（内存泄漏）
            try:
                # 计算在全局锁外执行，避免阻塞其他 query
                from apps.ai_model.embedding import EmbeddingModelCache
                model = EmbeddingModelCache.get_model()
                embedding = model.embed_query(query)
                result = tuple(embedding)

                import time as _time
                with self._lock:
                    if len(self._cache) >= self._maxsize:
                        oldest_key = next(iter(self._cache))
                        del self._cache[oldest_key]
                        self._timestamps.pop(oldest_key, None)
                    self._cache[query] = result
                    self._timestamps[query] = _time.time()

                return list(result)
            finally:
                # 无论成功或异常，都清理 per-query 锁
                with self._lock:
                    self._query_locks.pop(query, None)

    def clear(self):
        """模型热更新时调用，清空所有缓存的向量"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._query_locks.clear()


# 增大缓存容量，32 对于多用户并发场景太小
_embed_cache = _EmbeddingQueryCache(maxsize=256)


def search_document_chunks(
    session: Session,
    query: str,
    oid: int = 1,
    top_k: int = 5,
    similarity_threshold: float = 0.35,
    source_type: Optional[str] = None,
    ds_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """语义检索文档分块"""
    try:
        # 使用线程安全的手动缓存
        query_embedding = _embed_cache.get_or_compute(query)
    except Exception as e:
        ChatBILogUtil.error(f"文档检索向量化失败: {e}")
        return []

    try:
        # 空向量防御——embedding 模型返回全零或空列表时跳过检索
        if not query_embedding or all(x == 0 for x in query_embedding):
            ChatBILogUtil.warning(f"文档检索跳过: 查询向量为空或全零, query='{query[:50]}'")
            return []

        emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # ds_id 为 None 时记录警告，提示可能的数据隔离问题
        # 当 ds_id 未传入时，检索范围为整个工作空间的所有文档，可能跨数据源混合结果
        if ds_id is None:
            ChatBILogUtil.warning(
                f"文档检索未指定 ds_id，将搜索 oid={oid} 下所有文档。"
                f"多PDF场景下可能返回跨数据源的混合结果。query='{query[:50]}'"
            )

        # 显式排除 table_overlap 类型的分块（防御性过滤）
        sql_str = """SELECT
     c.id,
     c.text,
     c.source_type,
     c.source_name,
     c.source_file,
     c.section_title,
     c.page_number,
     c.chunk_type,
     c.info,
     c.library_id,
     d.filename,
     1 - (c.embedding <=> cast(:embedding AS vector)) AS similarity
FROM core_document_chunk c
JOIN core_document d ON c.document_id = d.id
WHERE d.oid = :oid
  AND c.embedding IS NOT NULL
  AND (c.chunk_type IS NULL OR c.chunk_type != 'table_overlap')
  AND 1 - (c.embedding <=> cast(:embedding AS vector)) >= :threshold"""
        
        params = {
            "embedding": emb_str,
            "oid": oid,
            "threshold": similarity_threshold,
            "top_k": top_k,
        }
        
        if source_type:
            sql_str += " AND c.source_type = :source_type"
            params["source_type"] = source_type
        
        if ds_id is not None:
            sql_str += " AND d.ds_id = :ds_id"
            params["ds_id"] = ds_id
        
        sql_str += " ORDER BY similarity DESC LIMIT :top_k"

        results = session.execute(text(sql_str), params).fetchall()

        # ds_id 指定但检索结果为空时，尝试自动修复关联
        if not results and ds_id is not None:
            try:
                from apps.datasource.models.datasource import CoreDatasource
                from apps.datasource.utils.utils import aes_decrypt
                import json as _json
                ds_record = session.query(CoreDatasource).filter(CoreDatasource.id == ds_id).first()
                if ds_record and ds_record.type and ds_record.type.lower() == 'pdf' and ds_record.configuration:
                    conf = _json.loads(aes_decrypt(ds_record.configuration))
                    doc_id = conf.get("document_id")
                    if doc_id:
                        from apps.datasource.models.document import CoreDocument
                        doc = session.query(CoreDocument).filter(CoreDocument.id == doc_id).first()
                        if doc and not doc.ds_id:
                            # 自动修复：回填 ds_id
                            doc.ds_id = ds_id
                            session.add(doc)
                            try:
                                session.commit()
                                ChatBILogUtil.warning(
                                    f"文档检索自动修复: doc_id={doc_id} 的 ds_id 为空，"
                                    f"已自动关联到 ds_id={ds_id}，重新执行检索"
                                )
                                # 重新执行检索
                                results = session.execute(text(sql_str), params).fetchall()
                            except Exception:
                                session.rollback()
            except Exception as repair_e:
                ChatBILogUtil.error(f"文档检索自动修复失败: {repair_e}")

        chunks = []
        for row in results:
            chunks.append({
                "id": row.id,
                "text": row.text,
                "source_type": row.source_type or "file",
                "source_name": row.source_name or row.source_file or row.filename,
                "info": row.info or "",
                "library_id": row.library_id,
                "source_file": row.source_file or row.filename,
                "section_title": row.section_title or "",
                "page_number": row.page_number,
                "chunk_type": row.chunk_type or "text",
                "similarity": round(float(row.similarity), 4),
                "filename": row.filename,
            })

        ChatBILogUtil.info(
            f"文档检索完成: query='{query[:50]}...', "
            f"results={len(chunks)}, "
            f"top_sim={chunks[0]['similarity'] if chunks else 0}"
        )
        return chunks

    except Exception as e:
        ChatBILogUtil.error(f"文档检索失败: {e}")
        return []


def format_document_context(chunks: List[Dict[str, Any]], max_tokens: int = 2000, lang: str = '简体中文') -> str:
    """将检索到的文档分块格式化为上下文文本。"""
    if not chunks:
        return ""

    is_english = 'english' in lang.lower() or lang.lower().startswith('en')

    context_parts = []
    total_len = 0

    # 将 import 和正则编译移到循环外部，避免每次迭代重复导入
    import re as _re
    _cn_pattern = _re.compile(r'[\u4e00-\u9fff]')
    _en_pattern = _re.compile(r'[a-zA-Z0-9]')

    # 按页码+chunk_index重排序，保证上下文连贯性
    chunks = sorted(
        chunks,
        key=lambda c: (
            c.get("page_number") if c.get("page_number") is not None else 99999,
            c.get("chunk_index", 0) if isinstance(c.get("chunk_index"), int) else 0,
        )
    )

    for i, chunk in enumerate(chunks):
        source = chunk.get("source_name", chunk.get("filename", "unknown"))
        source_type = chunk.get("source_type", "file")
        info = chunk.get("info", "")
        text_content = chunk.get("text", "")
        section_title = chunk.get("section_title", "")
        page_number = chunk.get("page_number")
        chunk_type = chunk.get("chunk_type", "text")
        similarity = chunk.get("similarity", 0)

        # 构建溯源标注（中英文适配）
        if is_english:
            source_tag_parts = [f"Source: {source}"]
            if page_number:
                source_tag_parts.append(f"Page {page_number}")
            if section_title:
                source_tag_parts.append(f"Section \"{section_title}\"")
            if chunk_type == "table":
                source_tag_parts.append("Table Data")
            if similarity > 0:
                source_tag_parts.append(f"Relevance {similarity:.0%}")
            source_tag = "[" + " - ".join(source_tag_parts) + "]"
            header = f"[Knowledge Fragment {i+1}] {source_tag}"
            if info:
                header += f"\nDescription: {info}"
        else:
            source_tag_parts = [f"来源: {source}"]
            if page_number:
                source_tag_parts.append(f"第{page_number}页")
            if section_title:
                source_tag_parts.append(f"章节「{section_title}」")
            if chunk_type == "table":
                source_tag_parts.append("表格数据")
            if similarity > 0:
                source_tag_parts.append(f"相关度{similarity:.0%}")
            source_tag = "【" + "-".join(source_tag_parts) + "】"
            header = f"[知识片段{i+1}] {source_tag}"
            if info:
                header += f"\n描述: {info}"

        entry = f"{header}\n{text_content}"

        # 使用与 context_compressor._estimate_tokens 一致的分组估算
        _cn = len(_cn_pattern.findall(entry))
        _en = len(_en_pattern.findall(entry))
        _other = len(entry) - _cn - _en
        entry_tokens = int(_cn * 1.5 + _en * 0.25 + _other * 0.5)

        if total_len + entry_tokens > max_tokens:
            break

        context_parts.append(entry)
        total_len += entry_tokens

    return "\n\n".join(context_parts)


def build_provenance_records(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从文档检索结果构建溯源凭证列表"""
    records = []
    for chunk in chunks:
        source_type = chunk.get("source_type", "file")
        record = {
            "source_type": source_type,
            "source_name": chunk.get("source_name", chunk.get("filename", "")),
            "similarity": round(chunk.get("similarity", 0), 4),
            "chunk_type": chunk.get("chunk_type", "text"),
        }

        # PDF溯源
        if chunk.get("page_number") is not None:
            record["page_number"] = chunk["page_number"]
        if chunk.get("section_title"):
            record["section_title"] = chunk["section_title"]

        # Excel/CSV溯源
        if chunk.get("sheet_name"):
            record["sheet_name"] = chunk["sheet_name"]
        if chunk.get("row_range"):
            record["row_range"] = chunk["row_range"]

        records.append(record)

    return records
