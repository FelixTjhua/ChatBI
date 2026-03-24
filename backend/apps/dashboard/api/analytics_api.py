"""系统分析仪表板 API"""
from datetime import datetime, timedelta
from fastapi import APIRouter
from sqlalchemy import func, and_, text
from apps.chat.models.chat_model import Chat, ChatRecord
from apps.datasource.models.datasource import CoreDatasource, CoreTable
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil

router = APIRouter(tags=["analytics"], prefix="/analytics")


def _get_oid(current_user: CurrentUser) -> int:
    """获取当前用户的工作空间 ID"""
    return current_user.oid if current_user.oid is not None else 1


@router.get("/overview")
async def get_system_overview(session: SessionDep, current_user: CurrentUser):
    """系统概览统计：数据源、知识库、对话、图表、用户"""
    # 所有统计查询按工作空间隔离，防止跨工作空间数据泄露
    oid = _get_oid(current_user)

    # 数据源总量（按工作空间）
    ds_count = session.query(func.count(CoreDatasource.id)).filter(
        CoreDatasource.oid == oid
    ).scalar() or 0

    # 数据表总量（按工作空间内的数据源）
    table_count = session.query(func.count(CoreTable.id)).filter(
        CoreTable.ds_id.in_(
            session.query(CoreDatasource.id).filter(CoreDatasource.oid == oid)
        )
    ).scalar() or 0

    # 知识库块数（半结构化知识·core_document_chunk）
    chunk_count = 0
    try:
        result = session.execute(
            text("SELECT COUNT(*) FROM core_document_chunk WHERE ds_id IN (SELECT id FROM core_datasource WHERE oid = :oid)"),
            {"oid": oid}
        )
        chunk_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count document chunks: {e}")
        session.rollback()

    # 商业术语数量（半结构化知识·business_term）
    terminology_count = 0
    try:
        result = session.execute(text("SELECT COUNT(*) FROM business_term"))
        terminology_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count terminologies: {e}")
        session.rollback()

    # SQL示例数量
    sql_example_count = 0
    try:
        result = session.execute(text("SELECT COUNT(*) FROM business_sql_example"))
        sql_example_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count SQL examples: {e}")
        session.rollback()

    # 对话总数（按工作空间）
    chat_count = session.query(func.count(Chat.id)).filter(
        Chat.oid == oid
    ).scalar() or 0

    # 消息总数（按工作空间内的对话）
    message_count = session.query(func.count(ChatRecord.id)).filter(
        and_(
            ChatRecord.first_chat == False,
            ChatRecord.chat_id.in_(
                session.query(Chat.id).filter(Chat.oid == oid)
            )
        )
    ).scalar() or 0

    # 图表生成次数（按工作空间内的对话）
    chart_count = session.query(func.count(ChatRecord.id)).filter(
        and_(
            ChatRecord.chart.isnot(None),
            ChatRecord.chart != '',
            ChatRecord.chat_id.in_(
                session.query(Chat.id).filter(Chat.oid == oid)
            )
        )
    ).scalar() or 0

    # 用户总数
    user_count = 0
    try:
        result = session.execute(text("SELECT COUNT(*) FROM sys_user"))
        user_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count users: {e}")
        session.rollback()

    # 模型配置状态（是否已配置AI模型）
    model_configured = False
    try:
        result = session.execute(
            text("SELECT COUNT(*) FROM ai_model")
        )
        model_configured = (result.scalar() or 0) > 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to check model config: {e}")
        session.rollback()

    # 最近操作时间（按工作空间）
    last_activity = None
    try:
        result = session.query(func.max(ChatRecord.create_time)).filter(
            and_(
                ChatRecord.first_chat == False,
                ChatRecord.chat_id.in_(
                    session.query(Chat.id).filter(Chat.oid == oid)
                )
            )
        ).scalar()
        if result:
            last_activity = result.isoformat()
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to get last activity: {e}")
        session.rollback()

    return {
        "datasource_count": ds_count,
        "table_count": table_count,
        "knowledge_chunk_count": chunk_count,
        "terminology_count": terminology_count,
        "sql_example_count": sql_example_count,
        "chat_count": chat_count,
        "message_count": message_count,
        "chart_count": chart_count,
        "user_count": user_count,
        "model_configured": model_configured,
        "last_activity": last_activity,
    }


@router.get("/datasource_stats")
async def get_datasource_stats(session: SessionDep, current_user: CurrentUser):
    """数据源统计：类型分布、表数量"""
    oid = _get_oid(current_user)

    # 按类型分组（按工作空间）
    type_dist = session.query(
        CoreDatasource.type, func.count(CoreDatasource.id)
    ).filter(CoreDatasource.oid == oid).group_by(CoreDatasource.type).all()

    # 最近上传的数据源（按工作空间）
    recent_ds = session.query(
        CoreDatasource.id, CoreDatasource.name, CoreDatasource.type, CoreDatasource.create_time
    ).filter(CoreDatasource.oid == oid).order_by(CoreDatasource.create_time.desc()).limit(5).all()

    # 每个数据源的表数量（按工作空间）
    table_counts = session.query(
        CoreTable.ds_id, func.count(CoreTable.id)
    ).filter(
        CoreTable.ds_id.in_(
            session.query(CoreDatasource.id).filter(CoreDatasource.oid == oid)
        )
    ).group_by(CoreTable.ds_id).all()

    return {
        "type_distribution": [{"type": t, "count": c} for t, c in type_dist],
        "recent_datasources": [
            {"id": r.id, "name": r.name, "type": r.type,
             "create_time": r.create_time.isoformat() if r.create_time else None}
            for r in recent_ds
        ],
        "table_counts": {str(ds_id): cnt for ds_id, cnt in table_counts},
    }


@router.get("/chat_stats")
async def get_chat_stats(session: SessionDep, current_user: CurrentUser):
    """对话行为分析：对话趋势、提问方式分布、意图分布"""
    oid = _get_oid(current_user)
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)

    # 工作空间内的对话 ID 子查询
    ws_chat_ids = session.query(Chat.id).filter(Chat.oid == oid)

    # 最近7天每天的对话数（按工作空间）
    daily_chats = session.query(
        func.date(ChatRecord.create_time).label('day'),
        func.count(ChatRecord.id)
    ).filter(
        and_(
            ChatRecord.create_time >= seven_days_ago,
            ChatRecord.first_chat == False,
            ChatRecord.chat_id.in_(ws_chat_ids)
        )
    ).group_by(func.date(ChatRecord.create_time)).order_by(
        func.date(ChatRecord.create_time)
    ).all()

    # 提问方式分布（按工作空间）
    input_type_dist = session.query(
        ChatRecord.input_type, func.count(ChatRecord.id)
    ).filter(
        and_(ChatRecord.first_chat == False, ChatRecord.chat_id.in_(ws_chat_ids))
    ).group_by(ChatRecord.input_type).all()

    # 意图分布（按工作空间）
    intent_dist = session.query(
        ChatRecord.intent, func.count(ChatRecord.id)
    ).filter(
        and_(
            ChatRecord.intent.isnot(None),
            ChatRecord.first_chat == False,
            ChatRecord.chat_id.in_(ws_chat_ids)
        )
    ).group_by(ChatRecord.intent).all()

    return {
        "daily_trend": [
            {"date": str(day), "count": cnt} for day, cnt in daily_chats
        ],
        "input_type_distribution": [
            {"type": t or "manual", "count": c} for t, c in input_type_dist
        ],
        "intent_distribution": [
            {"intent": i, "count": c} for i, c in intent_dist
        ],
    }


@router.get("/recent_conversations")
async def get_recent_conversations(session: SessionDep, current_user: CurrentUser):
    """最近对话与图表（4.5 第4项）：最近对话记录 + 最近生成的图表"""
    oid = _get_oid(current_user)
    ws_chat_ids = session.query(Chat.id).filter(Chat.oid == oid)

    # 最近10条对话记录（按工作空间）
    recent_records = session.query(
        ChatRecord.id, ChatRecord.chat_id, ChatRecord.question,
        ChatRecord.intent, ChatRecord.chart, ChatRecord.create_time
    ).filter(
        and_(
            ChatRecord.first_chat == False,
            ChatRecord.question.isnot(None),
            ChatRecord.chat_id.in_(ws_chat_ids)
        )
    ).order_by(ChatRecord.create_time.desc()).limit(10).all()

    conversations = []
    for r in recent_records:
        conversations.append({
            "id": r.id,
            "chat_id": r.chat_id,
            "question": (r.question[:50] + '...' if r.question and len(r.question) > 50 else r.question) or '',
            "intent": r.intent or '',
            "has_chart": bool(r.chart),
            "create_time": r.create_time.isoformat() if r.create_time else None,
        })

    return {"conversations": conversations}

@router.get("/knowledge_detail")
async def get_knowledge_detail(session: SessionDep, current_user: CurrentUser):
    """知识库详情（供仪表板点击查看）：文档列表、术语数、SQL示例数、文本块数"""
    oid = _get_oid(current_user)

    # 文档列表（按工作空间内的数据源）
    documents = []
    try:
        result = session.execute(text(
            "SELECT id, filename, file_type, total_chunks, create_time "
            "FROM core_document WHERE ds_id IN (SELECT id FROM core_datasource WHERE oid = :oid) "
            "ORDER BY create_time DESC LIMIT 50"
        ), {"oid": oid})
        for row in result:
            documents.append({
                "id": row[0],
                "filename": row[1],
                "file_type": row[2],
                "total_chunks": row[3] or 0,
                "create_time": row[4].isoformat() if row[4] else None,
            })
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to list documents: {e}")

    # 统计数据（按工作空间）
    chunk_count = 0
    try:
        result = session.execute(
            text("SELECT COUNT(*) FROM core_document_chunk WHERE ds_id IN (SELECT id FROM core_datasource WHERE oid = :oid)"),
            {"oid": oid}
        )
        chunk_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count chunks: {e}")

    document_count = len(documents)

    terminology_count = 0
    try:
        result = session.execute(text("SELECT COUNT(*) FROM business_term"))
        terminology_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count terminologies: {e}")

    sql_example_count = 0
    try:
        result = session.execute(text("SELECT COUNT(*) FROM business_sql_example"))
        sql_example_count = result.scalar() or 0
    except Exception as e:
        ChatBILogUtil.warning(f"[Analytics] Failed to count SQL examples: {e}")

    return {
        "document_count": document_count,
        "chunk_count": chunk_count,
        "terminology_count": terminology_count,
        "sql_example_count": sql_example_count,
        "documents": documents,
    }
