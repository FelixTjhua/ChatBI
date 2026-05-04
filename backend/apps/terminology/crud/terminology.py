import datetime
import logging
from typing import List, Optional, Any
from xml.dom.minidom import parseString

import dicttoxml
from sqlalchemy import and_, or_, select, func, delete, update, union, text
from sqlalchemy.orm import aliased

from apps.ai_model.embedding import EmbeddingModelCache
from apps.terminology.models.terminology_model import Terminology, TerminologyInfo
from apps.template.generate_chart.generator import get_base_terminology_template
from common.core.config import settings
from common.core.deps import SessionDep, Trans
from common.utils.embedding_threads import run_save_terminology_embeddings


def get_terminology_base_query(oid: int, name: Optional[str] = None):
    """
    获取术语查询的基础查询结构
    """
    child = aliased(Terminology)

    if name and name.strip() != "":
        keyword_pattern = f"%{name.strip()}%"
        # 步骤1：先找到所有匹配的节点ID（无论是父节点还是子节点）
        matched_ids_subquery = (
            select(Terminology.id)
            .where(and_(Terminology.word.ilike(keyword_pattern), Terminology.oid == oid))
            .subquery()
        )

        # 步骤2：找到这些匹配节点的所有父节点（包括自身如果是父节点）
        parent_ids_subquery = (
            select(Terminology.id)
            .where(
                (Terminology.id.in_(matched_ids_subquery)) |
                (Terminology.id.in_(
                    select(Terminology.pid)
                    .where(Terminology.id.in_(matched_ids_subquery))
                    .where(Terminology.pid.isnot(None))
                ))
            )
            .where(Terminology.pid.is_(None))  # 只取父节点
        )
    else:
        parent_ids_subquery = (
            select(Terminology.id)
            .where(and_(Terminology.pid.is_(None), Terminology.oid == oid))
        )

    return parent_ids_subquery, child


def build_terminology_query(session: SessionDep, oid: int, name: Optional[str] = None,
                            paginate: bool = True, current_page: int = 1, page_size: int = 10):
    """
    构建术语查询的通用方法
    """
    parent_ids_subquery, child = get_terminology_base_query(oid, name)

    # 计算总数
    count_stmt = select(func.count()).select_from(parent_ids_subquery.subquery())
    total_count = session.execute(count_stmt).scalar()

    if paginate:
        # 分页处理
        page_size = max(10, page_size)
        total_pages = (total_count + page_size - 1) // page_size
        current_page = max(1, min(current_page, total_pages)) if total_pages > 0 else 1

        paginated_parent_ids = (
            parent_ids_subquery
            .order_by(Terminology.create_time.desc())
            .offset((current_page - 1) * page_size)
            .limit(page_size)
            .subquery()
        )
    else:
        # 不分页，获取所有数据
        total_pages = 1
        current_page = 1
        page_size = total_count if total_count > 0 else 1

        paginated_parent_ids = (
            parent_ids_subquery
            .order_by(Terminology.create_time.desc())
            .subquery()
        )

    # 构建公共查询部分
    children_subquery = (
        select(
            child.pid,
            func.jsonb_agg(child.word).filter(child.word.isnot(None)).label('other_words')
        )
        .where(child.pid.isnot(None))
        .group_by(child.pid)
        .subquery()
    )

    stmt = (
        select(
            Terminology.id,
            Terminology.word,
            Terminology.create_time,
            Terminology.description,
            children_subquery.c.other_words,
            Terminology.enabled
        )
        .outerjoin(
            children_subquery,
            Terminology.id == children_subquery.c.pid
        )
        .where(and_(Terminology.id.in_(paginated_parent_ids), Terminology.oid == oid))
        .group_by(
            Terminology.id,
            Terminology.word,
            Terminology.create_time,
            Terminology.description,
            children_subquery.c.other_words,
            Terminology.enabled
        )
        .order_by(Terminology.create_time.desc())
    )

    return stmt, total_count, total_pages, current_page, page_size


def execute_terminology_query(session: SessionDep, stmt) -> List[TerminologyInfo]:
    """
    执行查询并返回术语信息列表
    """
    _list = []
    result = session.execute(stmt)

    for row in result:
        _list.append(TerminologyInfo(
            id=row.id,
            word=row.word,
            create_time=row.create_time,
            description=row.description,
            other_words=row.other_words if row.other_words else [],
            enabled=row.enabled if row.enabled is not None else False,
        ))

    return _list


def page_terminology(session: SessionDep, current_page: int = 1, page_size: int = 10,
                     name: Optional[str] = None, oid: Optional[int] = 1):
    """
    分页查询术语（原方法保持不变）
    """
    stmt, total_count, total_pages, current_page, page_size = build_terminology_query(
        session, oid, name, True, current_page, page_size
    )
    _list = execute_terminology_query(session, stmt)

    return current_page, page_size, total_count, total_pages, _list


def get_all_terminology(session: SessionDep, name: Optional[str] = None, oid: Optional[int] = 1):
    """
    获取所有术语（不分页）
    """
    stmt, total_count, total_pages, current_page, page_size = build_terminology_query(
        session, oid, name, False
    )
    _list = execute_terminology_query(session, stmt)

    return _list


def create_terminology(session: SessionDep, info: TerminologyInfo, oid: int, trans: Trans):
    create_time = datetime.datetime.now()

    parent = Terminology(word=info.word, create_time=create_time, description=info.description, oid=oid,
                         enabled=info.enabled)

    words = [info.word]
    for child in info.other_words:
        if child in words:
            raise Exception(trans("i18n_terminology.cannot_be_repeated"))
        else:
            words.append(child)

    # 基础查询条件（word 和 oid 必须满足）
    base_query = and_(
        Terminology.word.in_(words),
        Terminology.oid == oid
    )

    # 构建查询
    query = session.query(Terminology).filter(base_query)

    # 转换为 EXISTS 查询并获取结果
    exists = session.query(query.exists()).scalar()

    if exists:
        raise Exception(trans("i18n_terminology.exists_in_db"))

    result = Terminology(**parent.model_dump())

    session.add(parent)
    session.flush()
    session.refresh(parent)

    result.id = parent.id

    # 将父术语和子术语在同一个事务中提交，保证原子性
    _list: List[Terminology] = []
    if info.other_words:
        for other_word in info.other_words:
            if other_word.strip() == "":
                continue
            _list.append(
                Terminology(pid=result.id, word=other_word, create_time=create_time, oid=oid, enabled=result.enabled))
    if _list:
        session.bulk_save_objects(_list)
        session.flush()
    session.commit()

    # embedding
    run_save_terminology_embeddings([result.id])

    return result.id


def update_terminology(session: SessionDep, info: TerminologyInfo, oid: int, trans: Trans):
    count = session.query(Terminology).filter(
        Terminology.oid == oid,
        Terminology.id == info.id
    ).count()
    if count == 0:
        raise Exception(trans('i18n_terminology.terminology_not_exists'))

    words = [info.word]
    for child in info.other_words:
        if child in words:
            raise Exception(trans("i18n_terminology.cannot_be_repeated"))
        else:
            words.append(child)

    # 基础查询条件（word 和 oid 必须满足）
    base_query = and_(
        Terminology.word.in_(words),
        Terminology.oid == oid,
        or_(
            Terminology.pid != info.id,
            and_(Terminology.pid.is_(None), Terminology.id != info.id)
        ),
        Terminology.id != info.id
    )

    # 构建查询
    query = session.query(Terminology).filter(base_query)

    # 转换为 EXISTS 查询并获取结果
    exists = session.query(query.exists()).scalar()

    if exists:
        raise Exception(trans("i18n_terminology.exists_in_db"))

    # 将更新父术语、删除旧子术语、插入新子术语合并为单次事务
    stmt = update(Terminology).where(and_(Terminology.id == info.id)).values(
        word=info.word,
        description=info.description,
        enabled=info.enabled,
    )
    session.execute(stmt)

    stmt = delete(Terminology).where(and_(Terminology.pid == info.id))
    session.execute(stmt)

    create_time = datetime.datetime.now()
    _list: List[Terminology] = []
    if info.other_words:
        for other_word in info.other_words:
            if other_word.strip() == "":
                continue
            _list.append(
                Terminology(pid=info.id, word=other_word, create_time=create_time, oid=oid,
                            enabled=info.enabled))
    if _list:
        session.bulk_save_objects(_list)
        session.flush()
    session.commit()

    # embedding
    run_save_terminology_embeddings([info.id])

    return info.id


def delete_terminology(session: SessionDep, ids: list[int], oid: int = None):
    # 添加组织ID过滤，防止越权删除
    if oid is not None:
        stmt = delete(Terminology).where(and_(or_(Terminology.id.in_(ids), Terminology.pid.in_(ids)), Terminology.oid == oid))
    else:
        stmt = delete(Terminology).where(or_(Terminology.id.in_(ids), Terminology.pid.in_(ids)))
    session.execute(stmt)
    session.commit()


def enable_terminology(session: SessionDep, id: int, enabled: bool, trans: Trans):
    count = session.query(Terminology).filter(
        Terminology.id == id
    ).count()
    if count == 0:
        raise Exception(trans('i18n_terminology.terminology_not_exists'))

    stmt = update(Terminology).where(or_(Terminology.id == id, Terminology.pid == id)).values(
        enabled=enabled,
    )
    session.execute(stmt)
    session.commit()


def validate_terminology_hierarchy(session: SessionDep, oid: int) -> dict:
    """验证术语库父子关系完整性
        确保：
        """
    # 获取所有子术语（pid 非空）
    children = session.query(Terminology).filter(
        and_(Terminology.pid.isnot(None), Terminology.oid == oid)
    ).all()

    orphans = []
    deep_nesting = []

    parent_ids_cache = {}

    for child in children:
        # 检查父术语是否存在
        if child.pid not in parent_ids_cache:
            parent = session.query(Terminology).filter(
                Terminology.id == child.pid
            ).first()
            parent_ids_cache[child.pid] = parent

        parent = parent_ids_cache[child.pid]

        if parent is None:
            orphans.append({"id": child.id, "word": child.word, "pid": child.pid})
        elif parent.pid is not None:
            # 父术语自身也有 pid → 超过两级
            deep_nesting.append({
                "id": child.id, "word": child.word,
                "pid": child.pid, "parent_pid": parent.pid
            })

    return {
        "valid": len(orphans) == 0 and len(deep_nesting) == 0,
        "orphans": orphans,
        "deep_nesting": deep_nesting,
        "total_checked": len(children),
    }


def run_fill_empty_embeddings(session_maker):
    try:
        if not settings.EMBEDDING_ENABLED:
            return
        session = session_maker()
        stmt1 = select(Terminology.id).where(and_(Terminology.embedding.is_(None), Terminology.pid.is_(None)))
        stmt2 = select(Terminology.pid).where(
            and_(Terminology.embedding.is_(None), Terminology.pid.isnot(None))).distinct()
        combined_stmt = union(stmt1, stmt2)
        results = session.execute(combined_stmt).scalars().all()
        save_embeddings(session_maker, results)
    except Exception:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()


def save_embeddings(session_maker, ids: List[int]):
    if not settings.EMBEDDING_ENABLED:
        return

    if not ids or len(ids) == 0:
        return
    try:
        session = session_maker()
        _list = session.query(Terminology).filter(or_(Terminology.id.in_(ids), Terminology.pid.in_(ids))).all()

        _words_list = [item.word for item in _list]

        model = EmbeddingModelCache.get_model()

        results = model.embed_documents(_words_list)

        for index in range(len(results)):
            item = results[index]
            stmt = update(Terminology).where(and_(Terminology.id == _list[index].id)).values(embedding=item)
            session.execute(stmt)
        session.commit()

    except Exception:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()


embedding_sql = """WITH scored AS (
     SELECT t.id, t.pid, t.word,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_term t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.pid IS NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, pid, word, similarity
FROM scored"""

embedding_sql_with_datasource = """WITH scored AS (
     SELECT t.id, t.pid, t.word,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_term t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.pid IS NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, pid, word, similarity
FROM scored"""


def select_terminology_by_word(session: SessionDep, word: str, oid: int, datasource: int = None):
    # null/空字符串安全检查（与 select_terminology_by_word_with_details 对齐）
    if not word or not word.strip():
        return []

    # 转义 SQL 通配符，防止 ILIKE 注入（与 _with_details 变体对齐）
    safe_word = word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    _list: List[Terminology] = []

    stmt = (
        select(
            Terminology.id,
            Terminology.pid,
            Terminology.word,
        )
        .where(
            and_(text(":sentence ILIKE '%' || word || '%'"), Terminology.oid == oid, Terminology.enabled == True)
        )
    )

    # 执行查询
    params: dict[str, Any] = {'sentence': safe_word}

    results = session.execute(stmt, params).fetchall()

    for row in results:
        _list.append(Terminology(id=row.id, word=row.word, pid=row.pid))

    if settings.EMBEDDING_ENABLED:
        try:
            # 使用 begin_nested() 作为 savepoint，异常时自动回滚 savepoint
            # 这会回滚整个事务而非仅回滚 savepoint，导致之前的关键词匹配结果也丢失
            with session.begin_nested():
                # 使用共享的查询向量缓存，避免同一查询在术语检索和文档检索中重复计算 embedding
                from apps.datasource.document_retrieval import _embed_cache
                embedding = _embed_cache.get_or_compute(word)

                if datasource is not None:
                    results = session.execute(text(embedding_sql_with_datasource),
                                              {'embedding_array': str(embedding), 'oid': oid,
                                               'similarity_threshold': settings.EMBEDDING_TERMINOLOGY_SIMILARITY,
                                               'top_count': settings.EMBEDDING_TERMINOLOGY_TOP_COUNT}).fetchall()
                else:
                    results = session.execute(text(embedding_sql),
                                              {'embedding_array': str(embedding), 'oid': oid,
                                               'similarity_threshold': settings.EMBEDDING_TERMINOLOGY_SIMILARITY,
                                               'top_count': settings.EMBEDDING_TERMINOLOGY_TOP_COUNT}).fetchall()

                for row in results:
                    _list.append(Terminology(id=row.id, word=row.word, pid=row.pid))

        except Exception:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.exception()
            # begin_nested() 上下文管理器在异常时自动回滚 savepoint，无需手动 rollback

    _map: dict = {}
    _ids: list[int] = []
    for row in _list:
        if row.id in _ids or row.pid in _ids:
            continue
        if row.pid is not None:
            _ids.append(row.pid)
        else:
            _ids.append(row.id)

    if len(_ids) == 0:
        return []

    t_list = session.query(Terminology.id, Terminology.pid, Terminology.word, Terminology.description, Terminology.sql_mapping).filter(
        or_(Terminology.id.in_(_ids), Terminology.pid.in_(_ids))).all()
    for row in t_list:
        pid = str(row.pid) if row.pid is not None else str(row.id)
        if _map.get(pid) is None:
            _map[pid] = {'words': [], 'description': row.description, 'sql_mapping': row.sql_mapping or ''}
        _map[pid]['words'].append(row.word)

    _results: list[dict] = []
    for key in _map.keys():
        _results.append(_map.get(key))

    return _results


def get_example():
    _obj = {
        'terminologies': [
            {'words': ['GDP', '国内生产总值'],
             'description': '指在一个季度或一年，一个国家或地区的经济中所生产出的全部最终产品和劳务的价值。'},
        ]
    }
    return to_xml_string(_obj, 'example')


def to_xml_string(_dict: list[dict] | dict, root: str = 'terminologies') -> str:
    item_name_func = lambda x: 'terminology' if x == 'terminologies' else 'word' if x == 'words' else 'item'
    dicttoxml.LOG.setLevel(logging.ERROR)
    xml = dicttoxml.dicttoxml(_dict,
                              cdata=['word', 'description', 'sql_mapping'],
                              custom_root=root,
                              item_func=item_name_func,
                              xml_declaration=False,
                              encoding='utf-8',
                              attr_type=False).decode('utf-8')
    pretty_xml = parseString(xml).toprettyxml()

    if pretty_xml.startswith('<?xml'):
        end_index = pretty_xml.find('>') + 1
        pretty_xml = pretty_xml[end_index:].lstrip()

    # XML 反转义顺序 — &amp; 必须最后处理
    pretty_xml = pretty_xml.replace('&lt;', '<')
    pretty_xml = pretty_xml.replace('&gt;', '>')
    pretty_xml = pretty_xml.replace('&quot;', '"')
    pretty_xml = pretty_xml.replace('&apos;', "'")
    pretty_xml = pretty_xml.replace('&amp;', '&')

    return pretty_xml


def get_terminology_template(session: SessionDep, question: str, oid: Optional[int] = 1,
                             datasource: Optional[int] = None) -> str:
    if not oid:
        oid = 1
    _results = select_terminology_by_word(session, question, oid, datasource)
    if _results and len(_results) > 0:
        terminology = to_xml_string(_results)
        template = get_base_terminology_template().format(terminologies=terminology)
        return template
    else:
        return ''


def select_terminology_by_keyword_only(session: SessionDep, word: str, oid: int, datasource: int = None):
    """轻量级术语预取：仅关键词 ILIKE 匹配，不走向量检索。"""
    if not word or not word.strip():
        return []

    safe_word = word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    stmt = (
        select(
            Terminology.word,
            Terminology.description,
            Terminology.sql_mapping,
        )
        .where(
            and_(text(":sentence ILIKE '%' || word || '%'"), Terminology.oid == oid, Terminology.enabled == True)
        )
    )

    params: dict[str, Any] = {'sentence': safe_word}

    rows = session.execute(stmt, params).fetchall()
    return [
        {'word': r.word, 'description': r.description or '', 'sql_mapping': r.sql_mapping or ''}
        for r in rows
    ][:5]  # 前置预取最多5条，避免查询过长


def select_terminology_by_word_with_details(session: SessionDep, word: str, oid: int, datasource: int = None):
    """
    获取术语检索结果，包含相似度信息
    用于RAG效果测试展示
    """
    if not word or not word.strip():
        return []

    results_with_details = []

    # 关键词匹配
    safe_word = word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    stmt = (
        select(
            Terminology.id,
            Terminology.pid,
            Terminology.word,
            Terminology.description,
            Terminology.sql_mapping,
        )
        .where(
            and_(text(":sentence ILIKE '%' || word || '%'"), Terminology.oid == oid, Terminology.enabled == True)
        )
    )

    params: dict[str, Any] = {'sentence': safe_word}

    keyword_results = session.execute(stmt, params).fetchall()
    keyword_ids = set()

    for row in keyword_results:
        keyword_ids.add(row.id)
        results_with_details.append({
            'word': row.word,
            'description': row.description or '',
            'sql_mapping': row.sql_mapping or '',
            'similarity': 1.0,  # 统一使用 [0,1] 范围，关键词精确匹配为 1.0
            'match_type': 'keyword'
        })

    # 向量检索
    vector_ids = set()
    vector_id_pid = {}
    vector_id_detail = {}
    if settings.EMBEDDING_ENABLED:
        try:
            # 使用共享的查询向量缓存，避免同一查询重复计算 embedding
            from apps.datasource.document_retrieval import _embed_cache
            embedding = _embed_cache.get_or_compute(word)

            # 向量检索 SQL 增加 t.pid 字段，使向量命中的术语也能参与同义词聚合
            if datasource is not None:
                embedding_sql_detail = """WITH scored AS (
     SELECT t.id, t.pid, t.word, t.description, t.sql_mapping,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_term t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.pid IS NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, pid, word, description, sql_mapping, similarity FROM scored"""
                vector_results = session.execute(
                    text(embedding_sql_detail),
                    {
                        'embedding_array': str(embedding), 
                        'oid': oid, 
                        'similarity_threshold': settings.EMBEDDING_TERMINOLOGY_SIMILARITY,
                        'top_count': settings.EMBEDDING_TERMINOLOGY_TOP_COUNT
                    }
                ).fetchall()
            else:
                embedding_sql_detail = """WITH scored AS (
     SELECT t.id, t.pid, t.word, t.description, t.sql_mapping,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_term t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.pid IS NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, pid, word, description, sql_mapping, similarity FROM scored"""
                vector_results = session.execute(
                    text(embedding_sql_detail),
                    {
                        'embedding_array': str(embedding), 
                        'oid': oid,
                        'similarity_threshold': settings.EMBEDDING_TERMINOLOGY_SIMILARITY,
                        'top_count': settings.EMBEDDING_TERMINOLOGY_TOP_COUNT
                    }
                ).fetchall()

            for row in vector_results:
                if row.id not in keyword_ids:
                    results_with_details.append({
                        'word': row.word,
                        'description': row.description or '',
                        'sql_mapping': row.sql_mapping or '',
                        'similarity': round(float(row.similarity), 4),
                        'match_type': 'vector'
                    })
                    # 将向量命中的术语也纳入同义词聚合映射
                    vector_ids.add(row.id)
                    vector_id_pid[row.id] = row.pid
                    vector_id_detail[row.id] = {
                        'word': row.word,
                        'description': row.description or '',
                        'sql_mapping': row.sql_mapping or '',
                    }

        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.error(f"Vector search error: {e}")

    # 聚合同义词关系（与 select_terminology_by_word 保持一致）
    _id_to_pid = {}
    _id_to_detail = {}
    for row in keyword_results:
        _id_to_pid[row.id] = row.pid
        _id_to_detail[row.id] = {
            'word': row.word,
            'description': row.description or '',
            'sql_mapping': row.sql_mapping or '',
        }
    # 向量命中的术语也纳入映射
    for vid, vpid in vector_id_pid.items():
        if vid not in _id_to_pid:
            _id_to_pid[vid] = vpid
            if vid in vector_id_detail:
                _id_to_detail[vid] = vector_id_detail[vid]

    # 收集需要补充的父术语 ID（子术语命中时，需要拉取父术语及其所有子术语）
    _parent_ids_to_fetch = set()
    for tid, tpid in _id_to_pid.items():
        if tpid is not None:
            _parent_ids_to_fetch.add(tpid)

    # 查询父术语及其所有子术语，用于同义词聚合
    if _parent_ids_to_fetch:
        synonym_stmt = (
            select(
                Terminology.id,
                Terminology.pid,
                Terminology.word,
                Terminology.description,
                Terminology.sql_mapping,
            )
            .where(
                and_(
                    or_(Terminology.id.in_(_parent_ids_to_fetch), Terminology.pid.in_(_parent_ids_to_fetch)),
                    Terminology.oid == oid,
                    Terminology.enabled == True
                )
            )
        )
        synonym_results = session.execute(synonym_stmt).fetchall()
        for srow in synonym_results:
            if srow.id not in _id_to_pid:
                _id_to_pid[srow.id] = srow.pid
                _id_to_detail[srow.id] = {
                    'word': srow.word,
                    'description': srow.description or '',
                    'sql_mapping': srow.sql_mapping or '',
                }

    # 为每条结果补充同义词列表
    for item in results_with_details:
        # 查找该 word 对应的 id
        matched_id = None
        for tid, detail in _id_to_detail.items():
            if detail['word'] == item['word']:
                matched_id = tid
                break
        if matched_id is not None:
            pid = _id_to_pid.get(matched_id)
            parent_id = pid if pid is not None else matched_id
            # 收集同一父术语下的所有同义词
            synonyms = []
            for tid, tpid in _id_to_pid.items():
                if tid == parent_id or tpid == parent_id:
                    w = _id_to_detail.get(tid, {}).get('word', '')
                    if w and w != item['word']:
                        synonyms.append(w)
            if synonyms:
                item['synonyms'] = synonyms

    # 按相似度排序
    results_with_details.sort(key=lambda x: x['similarity'], reverse=True)
    
    # 检索阶段放宽到 15 条，让 reranker 的 top_k=5 做最终截断
    # 原硬编码 10 条截断发生在 rerank 之前，可能丢失高质量但排名靠后的术语
    return results_with_details[:15]
