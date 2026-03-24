# Author: Junjun
# Date: 2025/9/23
import json
import time

from apps.ai_model.embedding import EmbeddingModelCache
from apps.datasource.embedding.utils import cosine_similarity
from common.core.config import settings
from common.utils.utils import ChatBILogUtil


def get_table_embedding(tables: list[dict], question: str):
    _list = []
    for table in tables:
        _list.append({"id": table.get('id'), "schema_table": table.get('schema_table'), "cosine_similarity": 0.0})

    if _list:
        try:
            text = [s.get('schema_table') for s in _list]

            # 过滤空文本，embed_documents 传入空字符串会导致
            # 某些模型返回全零向量或抛异常
            if not all(text):
                text = [t or f"table_{i}" for i, t in enumerate(text)]

            model = EmbeddingModelCache.get_model()
            start_time = time.time()
            results = model.embed_documents(text)
            end_time = time.time()
            ChatBILogUtil.info(str(end_time - start_time))

            q_embedding = model.embed_query(question)
            for index in range(len(results)):
                item = results[index]
                _list[index]['cosine_similarity'] = cosine_similarity(q_embedding, item)

            _list.sort(key=lambda x: x['cosine_similarity'], reverse=True)
            _list = _list[:settings.TABLE_EMBEDDING_COUNT]
            # print(len(_list))
            ChatBILogUtil.info(json.dumps(_list))
            return _list
        except Exception:
            ChatBILogUtil.exception()
            # embedding 失败时返回原始列表（cosine_similarity=0.0），
            ChatBILogUtil.warning(
                f"get_table_embedding failed, returning {len(_list)} tables with similarity=0.0 (no ranking applied)"
            )
    return _list


def calc_table_embedding(tables: list[dict], question: str):
    _list = []
    for table in tables:
        _list.append(
            {"id": table.get('id'), "schema_table": table.get('schema_table'), "embedding": table.get('embedding'),
             "cosine_similarity": 0.0})

    if _list:
        try:
            # text = [s.get('schema_table') for s in _list]
            #
            model = EmbeddingModelCache.get_model()
            start_time = time.time()
            # results = model.embed_documents(text)
            results = [item.get('embedding') for item in _list]

            q_embedding = model.embed_query(question)
            for index in range(len(results)):
                item = results[index]
                # 安全解析 embedding，空字符串或 None 不调用 json.loads
                if item:
                    try:
                        parsed = json.loads(item) if isinstance(item, str) else item
                        _list[index]['cosine_similarity'] = cosine_similarity(q_embedding, parsed)
                    except (json.JSONDecodeError, TypeError):
                        _list[index]['cosine_similarity'] = 0.0

            _list.sort(key=lambda x: x['cosine_similarity'], reverse=True)
            _list = _list[:settings.TABLE_EMBEDDING_COUNT]
            # print(len(_list))
            end_time = time.time()
            ChatBILogUtil.info(str(end_time - start_time))
            ChatBILogUtil.info(json.dumps([{"id": ele.get('id'), "schema_table": ele.get('schema_table'),
                                            "cosine_similarity": ele.get('cosine_similarity')}
                                           for ele in _list]))
            return _list
        except Exception:
            ChatBILogUtil.exception()
    return _list
