# Author: Junjun
# Date: 2025/9/18
import json
import time
from typing import Optional

from apps.ai_model.embedding import EmbeddingModelCache
from apps.datasource.embedding.utils import cosine_similarity
from apps.datasource.models.datasource import CoreDatasource
from apps.system.crud.assistant import AssistantOutDs
from common.core.config import settings
from common.core.deps import CurrentAssistant
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil


def get_ds_embedding(session: SessionDep, current_user: CurrentUser, _ds_list, out_ds: AssistantOutDs,
                     question: str,
                     current_assistant: Optional[CurrentAssistant] = None):
    _list = []
    if current_assistant and current_assistant.type == 1:
        if out_ds.ds_list:
            for _ds in out_ds.ds_list:
                ds = out_ds.get_ds(_ds.id)
                # get_ds 可能返回 None（数据源已被删除）
                if ds is None:
                    continue
                table_schema = out_ds.get_db_schema(_ds.id, question, embedding=False)
                ds_info = f"{ds.name}, {ds.description}\n"
                ds_schema = ds_info + table_schema
                _list.append({"id": ds.id, "ds_schema": ds_schema, "cosine_similarity": 0.0, "ds": ds})

        if _list:
            try:
                text = [s.get('ds_schema') for s in _list]

                model = EmbeddingModelCache.get_model()
                results = model.embed_documents(text)

                q_embedding = model.embed_query(question)
                for index in range(len(results)):
                    item = results[index]
                    _list[index]['cosine_similarity'] = cosine_similarity(q_embedding, item)

                _list.sort(key=lambda x: x['cosine_similarity'], reverse=True)
                # print(len(_list))
                _list = _list[:settings.DS_EMBEDDING_COUNT]
                ChatBILogUtil.info(json.dumps(
                    [{"id": ele.get("id"), "name": ele.get("ds").name,
                      "cosine_similarity": ele.get("cosine_similarity")}
                     for ele in _list]))
                return [{"id": obj.get('ds').id, "name": obj.get('ds').name, "description": obj.get('ds').description}
                        for obj in _list]
            except Exception:
                ChatBILogUtil.exception()
                # embedding 失败时返回未排序的原始列表，而非静默返回空
                return [{"id": obj.get('ds').id, "name": obj.get('ds').name, "description": obj.get('ds').description}
                        for obj in _list if obj.get('ds')]
    else:
        for _ds in _ds_list:
            if _ds.get('id'):
                ds = session.get(CoreDatasource, _ds.get('id'))
                # session.get 可能返回 None（数据源已被删除），
                # 后续访问 ds.id / ds.name 会抛出 AttributeError
                if ds is None:
                    ChatBILogUtil.warning(f"数据源 {_ds.get('id')} 不存在，跳过")
                    continue
                # table_schema = get_table_schema(session, current_user, ds, question, embedding=False)
                _list.append({"id": ds.id, "cosine_similarity": 0.0, "ds": ds, "embedding": ds.embedding})

        if _list:
            try:
                # text = [s.get('ds_schema') for s in _list]

                model = EmbeddingModelCache.get_model()
                start_time = time.time()
                # results = model.embed_documents(text)
                results = [item.get('embedding') for item in _list]

                q_embedding = model.embed_query(question)
                for index in range(len(results)):
                    item = results[index]
                    if item:
                        try:
                            parsed = json.loads(item) if isinstance(item, str) else item
                            _list[index]['cosine_similarity'] = cosine_similarity(q_embedding, parsed)
                        except (json.JSONDecodeError, TypeError):
                            _list[index]['cosine_similarity'] = 0.0

                _list.sort(key=lambda x: x['cosine_similarity'], reverse=True)
                # print(len(_list))
                end_time = time.time()
                ChatBILogUtil.info(str(end_time - start_time))
                _list = _list[:settings.DS_EMBEDDING_COUNT]
                ChatBILogUtil.info(json.dumps(
                    [{"id": ele.get("id"), "name": ele.get("ds").name,
                      "cosine_similarity": ele.get("cosine_similarity")}
                     for ele in _list]))
                return [{"id": obj.get('ds').id, "name": obj.get('ds').name, "description": obj.get('ds').description}
                        for obj in _list]
            except Exception:
                ChatBILogUtil.exception()
                return [{"id": obj.get('ds').id, "name": obj.get('ds').name, "description": obj.get('ds').description}
                        for obj in _list if obj.get('ds')]
    return [{"id": obj.get('ds').id, "name": obj.get('ds').name, "description": obj.get('ds').description}
            for obj in _list if obj.get('ds')] if _list and _list[0].get('ds') else _list
