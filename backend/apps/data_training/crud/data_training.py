import datetime
import logging
import re
from typing import List, Optional
from xml.dom.minidom import parseString

import dicttoxml
from sqlalchemy import and_, select, func, delete, update, or_
from sqlalchemy import text

from apps.ai_model.embedding import EmbeddingModelCache
from apps.data_training.models.data_training_model import DataTrainingInfo, DataTraining, DataTrainingInfoResult
from apps.datasource.models.datasource import CoreDatasource
from apps.system.models.system_model import AssistantModel
from apps.template.generate_chart.generator import get_base_data_training_template
from common.core.config import settings
from common.core.deps import SessionDep, Trans
from common.utils.embedding_threads import run_save_data_training_embeddings


# ========== 分词级模糊匹配工具 ==========
_SEARCH_STOP_WORDS = frozenset({
    '用', '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己',
    '这', '他', '那', '被', '从', '她', '们', '把', '能', '让', '给', '它', '与', '及',
    '请', '帮我', '我想', '能不能', '可以', '麻烦', '一下', '看看', '查一下', '告诉我', '给我',
    '展示', '显示', '列出', '查询', '统计', '分析', '使用', '通过', '进行', '生成', '创建',
    '所有', '全部', '每个', '各个', '哪些', '什么', '怎么', '如何', '多少',
    '按照', '根据', '基于', '关于', '对于', '其中',
    '以及', '或者', '并且', '但是', '因为', '所以', '如果',
    '数据', '情况', '结果', '信息',
})

# 图表类型关键词（检索时忽略，因为SQL示例库的question通常不含图表类型）
_CHART_KEYWORDS = frozenset({
    '饼图', '柱状图', '折线图', '条形图', '表格', '图表', '散点图', '热力图',
    'pie', 'bar', 'line', 'chart', 'table', 'column', 'scatter', 'heatmap',
})


def _extract_search_tokens(question: str) -> List[str]:
    """从用户问题中提取核心业务词汇用于模糊检索"""
    if not question or not question.strip():
        return []
    
    q = question.strip()
    
    # 移除图表类型关键词
    for kw in _CHART_KEYWORDS:
        q = q.replace(kw, ' ')
    
    # 移除停用词
    for sw in _SEARCH_STOP_WORDS:
        q = q.replace(sw, ' ')
    
    # 按空格和标点分割，提取连续的中文片段和英文单词
    tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', q)
    
    # 去重保序
    seen = set()
    result = []
    for t in tokens:
        t_lower = t.lower()
        if t_lower not in seen and t_lower not in _SEARCH_STOP_WORDS:
            seen.add(t_lower)
            result.append(t)
    
    return result


def get_data_training_base_query(oid: int, name: Optional[str] = None):
    """
    获取数据训练查询的基础查询结构
    """
    if name and name.strip() != "":
        keyword_pattern = f"%{name.strip()}%"
        parent_ids_subquery = (
            select(DataTraining.id)
            .where(and_(DataTraining.question.ilike(keyword_pattern), DataTraining.oid == oid))
        )
    else:
        parent_ids_subquery = (
            select(DataTraining.id).where(and_(DataTraining.oid == oid))
        )

    return parent_ids_subquery


def build_data_training_query(session: SessionDep, oid: int, name: Optional[str] = None,
                              paginate: bool = True, current_page: int = 1, page_size: int = 10):
    """
    构建数据训练查询的通用方法
    """
    parent_ids_subquery = get_data_training_base_query(oid, name)

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
            .order_by(DataTraining.create_time.desc())
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
            .order_by(DataTraining.create_time.desc())
            .subquery()
        )

    # 构建主查询
    stmt = (
        select(
            DataTraining.id,
            DataTraining.oid,
            DataTraining.datasource,
            CoreDatasource.name,
            DataTraining.question,
            DataTraining.create_time,
            DataTraining.description,
            DataTraining.enabled,
            DataTraining.advanced_application,
            AssistantModel.name.label('advanced_application_name'),
        )
        .outerjoin(CoreDatasource, and_(DataTraining.datasource == CoreDatasource.id))
        .outerjoin(AssistantModel,
                   and_(DataTraining.advanced_application == AssistantModel.id, AssistantModel.type == 1))
        .where(and_(DataTraining.id.in_(paginated_parent_ids)))
        .order_by(DataTraining.create_time.desc())
    )

    return stmt, total_count, total_pages, current_page, page_size


def execute_data_training_query(session: SessionDep, stmt) -> List[DataTrainingInfoResult]:
    """
    执行查询并返回数据训练信息列表
    """
    _list = []
    result = session.execute(stmt)

    for row in result:
        _list.append(DataTrainingInfoResult(
            id=str(row.id),
            oid=str(row.oid),
            datasource=row.datasource,
            datasource_name=row.name,
            question=row.question,
            create_time=row.create_time,
            description=row.description,
            enabled=row.enabled,
            advanced_application=str(row.advanced_application) if row.advanced_application else None,
            advanced_application_name=row.advanced_application_name,
        ))

    return _list


def page_data_training(session: SessionDep, current_page: int = 1, page_size: int = 10,
                       name: Optional[str] = None, oid: Optional[int] = 1):
    """
    分页查询数据训练（原方法保持不变）
    """
    stmt, total_count, total_pages, current_page, page_size = build_data_training_query(
        session, oid, name, True, current_page, page_size
    )
    _list = execute_data_training_query(session, stmt)

    return current_page, page_size, total_count, total_pages, _list


def get_all_data_training(session: SessionDep, name: Optional[str] = None, oid: Optional[int] = 1):
    """
    获取所有数据训练（不分页）
    """
    stmt, total_count, total_pages, current_page, page_size = build_data_training_query(
        session, oid, name, False
    )
    _list = execute_data_training_query(session, stmt)

    return _list


def create_training(session: SessionDep, info: DataTrainingInfo, oid: int, trans: Trans):
    create_time = datetime.datetime.now()

    parent = DataTraining(question=info.question, create_time=create_time, description=info.description, oid=oid,
                          datasource=info.datasource,
                          enabled=info.enabled,
                          advanced_application=info.advanced_application)

    stmt = select(DataTraining.id).where(and_(DataTraining.question == info.question, DataTraining.oid == oid))

    if info.datasource and info.advanced_application is not None:
        stmt = stmt.where(
            or_(DataTraining.datasource == info.datasource,
                DataTraining.advanced_application == info.advanced_application))
    elif info.datasource and info.advanced_application is None:
        stmt = stmt.where(and_(DataTraining.datasource == info.datasource))
    elif not info.datasource and info.advanced_application is not None:
        stmt = stmt.where(and_(DataTraining.advanced_application == info.advanced_application))

    exists = session.query(stmt.exists()).scalar()

    if exists:
        raise Exception(trans("i18n_data_training.exists_in_db"))

    result = DataTraining(**parent.model_dump())

    session.add(parent)
    session.flush()
    session.refresh(parent)

    result.id = parent.id
    session.commit()

    # embedding
    run_save_data_training_embeddings([result.id])

    return result.id


def update_training(session: SessionDep, info: DataTrainingInfo, oid: int, trans: Trans):
    count = session.query(DataTraining).filter(
        DataTraining.id == info.id
    ).count()
    if count == 0:
        raise Exception(trans('i18n_data_training.data_training_not_exists'))

    stmt = select(DataTraining.id).where(
        and_(DataTraining.question == info.question, DataTraining.oid == oid, DataTraining.id != info.id))

    if info.datasource and info.advanced_application is not None:
        stmt = stmt.where(
            or_(DataTraining.datasource == info.datasource,
                DataTraining.advanced_application == info.advanced_application))
    elif info.datasource and info.advanced_application is None:
        stmt = stmt.where(and_(DataTraining.datasource == info.datasource))
    elif not info.datasource and info.advanced_application is not None:
        stmt = stmt.where(and_(DataTraining.advanced_application == info.advanced_application))

    exists = session.query(stmt.exists()).scalar()

    if exists:
        raise Exception(trans("i18n_data_training.exists_in_db"))

    stmt = update(DataTraining).where(and_(DataTraining.id == info.id)).values(
        question=info.question,
        description=info.description,
        datasource=info.datasource,
        enabled=info.enabled,
        advanced_application=info.advanced_application,
    )
    session.execute(stmt)
    session.commit()

    # embedding
    run_save_data_training_embeddings([info.id])

    return info.id


def delete_training(session: SessionDep, ids: list[int], oid: int = None):
    # 添加组织ID过滤，防止越权删除
    if oid is not None:
        stmt = delete(DataTraining).where(and_(DataTraining.id.in_(ids), DataTraining.oid == oid))
    else:
        stmt = delete(DataTraining).where(and_(DataTraining.id.in_(ids)))
    session.execute(stmt)
    session.commit()


def enable_training(session: SessionDep, id: int, enabled: bool, trans: Trans):
    count = session.query(DataTraining).filter(
        DataTraining.id == id
    ).count()
    if count == 0:
        raise Exception(trans('i18n_data_training.data_training_not_exists'))

    stmt = update(DataTraining).where(and_(DataTraining.id == id)).values(
        enabled=enabled,
    )
    session.execute(stmt)
    session.commit()


def run_fill_empty_embeddings(session_maker):
    try:
        if not settings.EMBEDDING_ENABLED:
            return

        session = session_maker()
        stmt = select(DataTraining.id).where(and_(DataTraining.embedding.is_(None)))
        results = session.execute(stmt).scalars().all()

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
        _list = session.query(DataTraining).filter(and_(DataTraining.id.in_(ids))).all()

        _question_list = [item.question for item in _list]

        model = EmbeddingModelCache.get_model()

        results = model.embed_documents(_question_list)

        for index in range(len(results)):
            item = results[index]
            stmt = update(DataTraining).where(and_(DataTraining.id == _list[index].id)).values(embedding=item)
            session.execute(stmt)
        session.commit()

    except Exception:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()
    finally:
        session_maker.remove()


embedding_sql = """WITH scored AS (
     SELECT t.id, t.datasource, t.question,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= 0.28
       AND (t.datasource = :datasource OR t.datasource IS NULL)
     ORDER BY similarity DESC
     LIMIT 8
)
SELECT id, datasource, question, similarity
FROM scored"""

embedding_sql_in_advanced_application = """WITH scored AS (
     SELECT t.id, t.advanced_application, t.question,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND t.advanced_application = :advanced_application
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= 0.28
     ORDER BY similarity DESC
     LIMIT 8
)
SELECT id, advanced_application, question, similarity FROM scored"""


def _build_ds_scope_filter(datasource, advanced_application_id):
    """构建数据源范围过滤条件，供多个检索函数复用"""
    if advanced_application_id is not None:
        return or_(
            DataTraining.advanced_application.is_(None),
            DataTraining.advanced_application == advanced_application_id
        )
    elif datasource is not None:
        return or_(
            DataTraining.datasource.is_(None),
            DataTraining.datasource == datasource
        )
    else:
        return DataTraining.enabled == True  # 无额外过滤


def _token_fuzzy_match(session: SessionDep, question: str, oid: int,
                       datasource: Optional[int] = None,
                       advanced_application_id: Optional[int] = None,
                       exclude_ids: set = None) -> List[dict]:
    """分词级模糊匹配：提取核心业务词汇，要求示例question包含至少2个关键词
    
    解决 ILIKE 子串匹配对长句子命中率低的问题。
    例如"用饼图展示各产品类别的销售额占比"经分词后提取["产品类别","销售额","占比"]，
    只要示例question包含其中>=2个词就算命中。
    """
    tokens = _extract_search_tokens(question)
    if len(tokens) < 2:
        return []
    
    exclude_ids = exclude_ids or set()
    
    # 构建 token ILIKE 条件：question ILIKE '%token%'
    # 要求至少命中 min_match 个 token
    min_match = min(2, len(tokens))
    
    # 用 SQL CASE 表达式计算每条记录命中的 token 数量
    case_parts = []
    params = {'oid': oid}
    for i, token in enumerate(tokens):
        safe_token = token.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        param_name = f'tok_{i}'
        params[param_name] = safe_token
        case_parts.append(f"CASE WHEN question ILIKE '%' || :{param_name} || '%' THEN 1 ELSE 0 END")
    
    match_count_expr = ' + '.join(case_parts)
    
    # 构建数据源范围过滤 SQL
    ds_filter_sql = ""
    if advanced_application_id is not None:
        ds_filter_sql = "AND (advanced_application IS NULL OR advanced_application = :adv_app_id)"
        params['adv_app_id'] = advanced_application_id
    elif datasource is not None:
        ds_filter_sql = "AND (datasource IS NULL OR datasource = :datasource_id)"
        params['datasource_id'] = datasource
    
    sql = f"""SELECT id, question, match_count FROM (
    SELECT id, question, ({match_count_expr}) as match_count
    FROM business_sql_example
    WHERE oid = :oid AND enabled = true {ds_filter_sql}
    ) sub
    WHERE match_count >= {min_match}
    ORDER BY match_count DESC
    LIMIT 5"""
    
    try:
        results = session.execute(text(sql), params).fetchall()
        matched = []
        for row in results:
            if row.id not in exclude_ids:
                matched.append({
                    'id': row.id,
                    'question': row.question,
                    'match_count': row.match_count,
                })
        return matched
    except Exception:
        from common.utils.utils import ChatBILogUtil
        ChatBILogUtil.exception()
        return []


def select_training_by_question(session: SessionDep, question: str, oid: int, datasource: Optional[int] = None,
                                advanced_application_id: Optional[int] = None):
    """智能SQL示例检索策略（三通道混合检索）"""
    # null/空字符串安全检查（与 terminology.py 对齐）
    if not question or not question.strip():
        return []

    # 转义 SQL 通配符，防止 ILIKE 注入（与 terminology.py 对齐）
    safe_question = question.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    _list: List[DataTraining] = []

    # ========== 通道1：ILIKE 子串匹配（原有逻辑）==========
    stmt = (
        select(
            DataTraining.id,
            DataTraining.question,
        )
        .where(
            and_(or_(text(":sentence ILIKE '%' || question || '%'"), text("question ILIKE '%' || :sentence || '%'")),
                 DataTraining.oid == oid,
                 DataTraining.enabled == True)
        )
    )
    
    ds_scope = _build_ds_scope_filter(datasource, advanced_application_id)
    stmt = stmt.where(ds_scope)

    params = {'sentence': safe_question}
    if datasource is not None:
        params['datasource_id'] = datasource
    
    results = session.execute(stmt, params).fetchall()

    for row in results:
        _list.append(DataTraining(id=row.id, question=row.question))

    # ========== 通道2：分词级模糊匹配（新增）==========
    existing_ids = {item.id for item in _list}
    token_matches = _token_fuzzy_match(
        session, question, oid, datasource, advanced_application_id, exclude_ids=existing_ids
    )
    for m in token_matches:
        _list.append(DataTraining(id=m['id'], question=m['question']))

    if settings.EMBEDDING_ENABLED:
        with session.begin_nested():
            try:
                # 使用共享的查询向量缓存，避免同一查询在术语检索和SQL示例检索中重复计算 embedding
                from apps.datasource.document_retrieval import _embed_cache
                embedding = _embed_cache.get_or_compute(question)

                if advanced_application_id is not None:
                    results = session.execute(text(embedding_sql_in_advanced_application),
                                              {'embedding_array': str(embedding), 'oid': oid,
                                               'advanced_application': advanced_application_id})
                elif datasource is not None:
                    results = session.execute(text(embedding_sql),
                                              {'embedding_array': str(embedding), 'oid': oid, 'datasource': datasource})
                else:
                    # 没有指定数据源时，只检索全局知识库
                    global_embedding_sql = """WITH scored AS (
     SELECT t.id, t.datasource, t.question,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= 0.28
     ORDER BY similarity DESC
     LIMIT 8
)
SELECT id, datasource, question, similarity FROM scored"""
                    results = session.execute(text(global_embedding_sql),
                                              {'embedding_array': str(embedding), 'oid': oid})

                for row in results:
                    _list.append(DataTraining(id=row.id, question=row.question))

            except Exception:
                from common.utils.utils import ChatBILogUtil
                ChatBILogUtil.exception()
                # begin_nested() 上下文管理器在异常时自动回滚 savepoint，无需手动 rollback
                # 移除 session.rollback()，避免回滚整个事务而非仅回滚 savepoint

    # 去重
    _map: dict = {}
    _ids: list[int] = []
    
    for row in _list:
        if row.id in _ids:
            continue
        else:
            _ids.append(row.id)

    if len(_ids) == 0:
        return []

    t_list = session.query(DataTraining.id, DataTraining.question, DataTraining.description).filter(
        and_(DataTraining.id.in_(_ids))).all()

    for row in t_list:
        _map[row.id] = {
            'question': row.question, 
            'suggestion-answer': row.description,
        }

    _results: list[dict] = []
    for key, value in _map.items():
        _results.append({
            'question': value['question'],
            'suggestion-answer': value['suggestion-answer']
        })

    return _results


def to_xml_string(_dict: list[dict] | dict, root: str = 'sql-examples') -> str:
    item_name_func = lambda x: 'sql-example' if x == 'sql-examples' else 'item'
    dicttoxml.LOG.setLevel(logging.ERROR)
    xml = dicttoxml.dicttoxml(_dict,
                              cdata=['question', 'suggestion-answer'],
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
    # 如果先替换 &amp; → &，则 &lt; 会变成 <（被二次替换）
    pretty_xml = pretty_xml.replace('&lt;', '<')
    pretty_xml = pretty_xml.replace('&gt;', '>')
    pretty_xml = pretty_xml.replace('&quot;', '"')
    pretty_xml = pretty_xml.replace('&apos;', "'")
    pretty_xml = pretty_xml.replace('&amp;', '&')

    return pretty_xml


def get_training_template(session: SessionDep, question: str, oid: Optional[int] = 1, datasource: Optional[int] = None,
                          advanced_application_id: Optional[int] = None) -> str:
    if not oid:
        oid = 1
    if not datasource and not advanced_application_id:
        return ''
    _results = select_training_by_question(session, question, oid, datasource, advanced_application_id)
    if _results and len(_results) > 0:
        data_training = to_xml_string(_results)
        template = get_base_data_training_template().format(data_training=data_training)
        return template
    else:
        return ''


def select_training_by_question_with_details(session: SessionDep, question: str, oid: int, 
                                              datasource: Optional[int] = None,
                                              advanced_application_id: Optional[int] = None):
    """
    获取SQL示例检索结果，包含相似度信息（三通道混合检索）
    
    通道1：ILIKE 子串匹配（精确）
    通道2：分词级模糊匹配（宽松，解决长句子命中率低的问题）
    通道3：向量语义检索（语义相似度）
    """
    # null/空字符串安全检查
    if not question or not question.strip():
        return []

    # 转义 SQL 通配符，防止 ILIKE 注入
    safe_question = question.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    results_with_details = []

    # ========== 通道1：ILIKE 子串匹配（原有逻辑）==========
    stmt = (
        select(
            DataTraining.id,
            DataTraining.question,
            DataTraining.description,
        )
        .where(
            and_(or_(text(":sentence ILIKE '%' || question || '%'"), text("question ILIKE '%' || :sentence || '%'")),
                 DataTraining.oid == oid,
                 DataTraining.enabled == True)
        )
    )
    
    ds_scope = _build_ds_scope_filter(datasource, advanced_application_id)
    stmt = stmt.where(ds_scope)

    params = {'sentence': safe_question}
    if datasource is not None:
        params['datasource_id'] = datasource
    
    keyword_results = session.execute(stmt, params).fetchall()
    keyword_ids = set()

    for row in keyword_results:
        keyword_ids.add(row.id)
        results_with_details.append({
            'question': row.question,
            'sql': row.description or '',
            'similarity': 1.0,
            'match_type': 'substring'
        })

    # ========== 通道2：分词级模糊匹配（新增）==========
    token_matches = _token_fuzzy_match(
        session, question, oid, datasource, advanced_application_id, exclude_ids=keyword_ids
    )
    for m in token_matches:
        keyword_ids.add(m['id'])
        # 根据命中token数量计算相似度分数（0.7~0.9区间）
        tokens = _extract_search_tokens(question)
        token_sim = min(0.9, 0.7 + 0.05 * m.get('match_count', 2)) if tokens else 0.8
        # 需要查询 description
        desc_row = session.execute(
            select(DataTraining.description).where(DataTraining.id == m['id'])
        ).first()
        results_with_details.append({
            'question': m['question'],
            'sql': desc_row.description if desc_row and desc_row.description else '',
            'similarity': round(token_sim, 4),
            'match_type': 'token_fuzzy'
        })

    # 向量检索
    if settings.EMBEDDING_ENABLED:
        try:
            # 使用共享的查询向量缓存，避免同一查询重复计算 embedding
            from apps.datasource.document_retrieval import _embed_cache
            embedding = _embed_cache.get_or_compute(question)

            # 使用 CTE 避免重复计算余弦距离（与 terminology.py 对齐）
            embedding_sql_detail = ""
            
            # 修改查询逻辑
            if datasource is not None:
                embedding_sql_detail = """WITH scored AS (
     SELECT t.id, t.question, t.description,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
       AND (t.datasource IS NULL OR t.datasource = :datasource)
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, question, description, similarity FROM scored"""
            elif advanced_application_id is not None:
                embedding_sql_detail = """WITH scored AS (
     SELECT t.id, t.question, t.description,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND t.advanced_application = :advanced_application
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, question, description, similarity FROM scored"""
            else:
                embedding_sql_detail = """WITH scored AS (
     SELECT t.id, t.question, t.description,
            1 - (t.embedding <=> cast(:embedding_array AS vector)) AS similarity
     FROM business_sql_example t
     WHERE t.oid = :oid
       AND t.embedding IS NOT NULL
       AND t.enabled = true
       AND 1 - (t.embedding <=> cast(:embedding_array AS vector)) >= :similarity_threshold
     ORDER BY similarity DESC
     LIMIT :top_count
)
SELECT id, question, description, similarity FROM scored"""

            params = {
                'embedding_array': str(embedding), 
                'oid': oid,
                'similarity_threshold': settings.EMBEDDING_DATA_TRAINING_SIMILARITY,
                'top_count': settings.EMBEDDING_DATA_TRAINING_TOP_COUNT
            }
            if datasource is not None:
                params['datasource'] = datasource
            if advanced_application_id is not None:
                params['advanced_application'] = advanced_application_id

            vector_results = session.execute(text(embedding_sql_detail), params).fetchall()

            for row in vector_results:
                if row.id not in keyword_ids:
                    results_with_details.append({
                        'question': row.question,
                        'sql': row.description or '',
                        'similarity': round(float(row.similarity), 4),  # 统一使用 [0,1] 范围，不再乘以100
                        'match_type': 'vector'
                    })

        except Exception as e:
            from common.utils.utils import ChatBILogUtil
            ChatBILogUtil.error(f"Vector search error: {e}")

    # 按相似度排序
    results_with_details.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results_with_details[:10]  # 最多返回10条
