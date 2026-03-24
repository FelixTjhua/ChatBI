from sqlalchemy import select, and_, text
from apps.dashboard.models.dashboard_model import CoreDashboard, CreateDashboard, QueryDashboard, DashboardBaseResponse
from common.core.deps import SessionDep, CurrentUser
import uuid
import time
import json
import logging

from common.utils.tree_utils import build_tree_generic
from common.utils.locale import I18n

_i18n = I18n("locales")


def _dash_trans(user=None) -> callable:
    """获取基于用户语言的翻译函数"""
    lang = (user.language if user and hasattr(user, 'language') else 'zh-CN') or 'zh-CN'
    _lang = lang.lower().replace('_', '-')
    translations = _i18n.translations.get(_lang, _i18n.translations.get('zh-cn', {}))
    def _t(key: str, **kwargs) -> str:
        keys = key.split('.')
        current = translations
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return key
        if isinstance(current, str) and kwargs:
            try:
                return current.format(**kwargs)
            except (KeyError, ValueError):
                return current
        return current if isinstance(current, str) else key
    return _t

logger = logging.getLogger(__name__)


def list_resource(session: SessionDep, dashboard: QueryDashboard, current_user: CurrentUser):
    sql = "SELECT id, name, type, node_type, pid, create_time, update_time, component_data FROM core_dashboard"
    filters = []
    params = {}
    oid = str(current_user.oid if current_user.oid is not None else 1)
    filters.append("workspace_id = :workspace_id")
    filters.append("create_by = :create_by")
    params["workspace_id"] = oid
    params["create_by"] = str(current_user.id)
    if dashboard.node_type is not None and dashboard.node_type != "":
        filters.append("node_type = :node_type")
        params["node_type"] = dashboard.node_type

    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY create_time DESC"
    result = session.execute(text(sql), params)
    nodes = [DashboardBaseResponse(**row) for row in result.mappings()]
    tree = build_tree_generic(nodes, root_pid="root")
    return tree


def load_resource(session: SessionDep, dashboard: QueryDashboard, current_user: CurrentUser):
    """加载资源，包含权限验证"""
    oid = str(current_user.oid if current_user.oid is not None else 1)
    uid = str(current_user.id)
    
    sql = text("""SELECT cd.*,
    creator.name AS create_name,
    """)
    result = session.execute(sql, {
        "dashboard_id": dashboard.id,
        "workspace_id": oid,
        "create_by": uid
    }).mappings().first()
    return result


def get_create_base_info(user: CurrentUser, dashboard: CreateDashboard):
    new_id = uuid.uuid4().hex
    record = CoreDashboard(**dashboard.model_dump())
    record.workspace_id = str(user.oid if user.oid is not None else 1)
    record.id = new_id
    record.create_by = str(user.id)
    record.create_time = int(time.time())
    return record


def create_resource(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    record = get_create_base_info(user, dashboard)
    session.add(record)
    session.flush()
    session.refresh(record)
    session.commit()
    return record


def update_resource(session: SessionDep, user: CurrentUser, dashboard: QueryDashboard):
    record = session.query(CoreDashboard).filter(CoreDashboard.id == dashboard.id).first()
    if not record:
        raise ValueError("Resource not found")
    # 验证资源所有权，防止越权修改
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)
    if record.workspace_id != oid or record.create_by != uid:
        raise ValueError("No permission to update this resource")
    record.name = dashboard.name
    record.update_by = user.id
    record.update_time = int(time.time())
    session.add(record)
    session.commit()
    return record


def create_canvas(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    record = get_create_base_info(user, dashboard)
    record.node_type = dashboard.node_type
    record.component_data = dashboard.component_data
    record.canvas_style_data = dashboard.canvas_style_data
    record.canvas_view_info = dashboard.canvas_view_info
    session.add(record)
    session.flush()
    session.refresh(record)
    session.commit()
    return record


def update_canvas(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    record = session.query(CoreDashboard).filter(CoreDashboard.id == dashboard.id).first()
    if not record:
        raise ValueError("Canvas not found")
    # 验证资源所有权，防止越权修改
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)
    if record.workspace_id != oid or record.create_by != uid:
        raise ValueError("No permission to update this canvas")
    record.name = dashboard.name
    record.update_by = user.id
    record.update_time = int(time.time())
    record.component_data = dashboard.component_data
    record.canvas_style_data = dashboard.canvas_style_data
    record.canvas_view_info = dashboard.canvas_view_info
    session.add(record)
    session.commit()
    return record


def validate_name(session: SessionDep,user: CurrentUser,  dashboard: QueryDashboard) -> bool:
    if not dashboard.opt:
        raise ValueError("opt is required")
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)


    if dashboard.opt in ('newLeaf', 'newFolder'):
        query = session.query(CoreDashboard).filter(
            and_(
                CoreDashboard.workspace_id == oid,
                CoreDashboard.create_by == uid,
                CoreDashboard.name == dashboard.name
            )
        )
    elif dashboard.opt in ('updateLeaf', 'updateFolder', 'rename'):
        if not dashboard.id:
            raise ValueError("id is required for update operation")
        query = session.query(CoreDashboard).filter(
            and_(
                CoreDashboard.workspace_id == oid,
                CoreDashboard.create_by == uid,
                CoreDashboard.name == dashboard.name,
                CoreDashboard.id != dashboard.id
            )
        )
    else:
        raise ValueError(f"Invalid opt value: {dashboard.opt}")
    return not session.query(query.exists()).scalar()


def delete_resource(session: SessionDep, resource_id: str, user: CurrentUser = None):
    # 验证资源存在且属于当前用户
    resource = session.query(CoreDashboard).filter(CoreDashboard.id == resource_id).first()
    if not resource:
        return False
    
    # 验证资源所有权，防止越权删除
    if user:
        oid = str(user.oid if user.oid is not None else 1)
        uid = str(user.id)
        if resource.workspace_id != oid or resource.create_by != uid:
            raise ValueError("No permission to delete this resource")
    
    if resource.node_type == 'folder':
        # 递归删除所有子资源
        def delete_children(pid: str):
            children = session.query(CoreDashboard).filter(CoreDashboard.pid == pid).all()
            for child in children:
                if child.node_type == 'folder':
                    delete_children(child.id)
                session.delete(child)
        delete_children(resource_id)
    
    # 删除当前资源（统一使用ORM方式）
    if resource:
        session.delete(resource)
        session.commit()
        return True
    return False


def move_resource(session: SessionDep, user: CurrentUser, dashboard: QueryDashboard):
    """移动资源到新的父节点"""
    if not dashboard.id or not dashboard.pid:
        raise ValueError("id and pid are required")
    
    # 验证资源存在且属于当前用户
    resource = session.query(CoreDashboard).filter(
        and_(
            CoreDashboard.id == dashboard.id,
            CoreDashboard.workspace_id == str(user.oid if user.oid is not None else 1),
            CoreDashboard.create_by == str(user.id)
        )
    ).first()
    
    if not resource:
        raise ValueError("Resource not found or access denied")
    
    # 验证目标父节点存在（如果不是root）
    if dashboard.pid != 'root':
        parent = session.query(CoreDashboard).filter(
            and_(
                CoreDashboard.id == dashboard.pid,
                CoreDashboard.node_type == 'folder',
                CoreDashboard.workspace_id == str(user.oid if user.oid is not None else 1)
            )
        ).first()
        
        if not parent:
            raise ValueError("Parent folder not found")
    
    # 更新父节点
    resource.pid = dashboard.pid
    resource.update_by = str(user.id)
    resource.update_time = int(time.time())
    
    session.add(resource)
    session.commit()
    session.refresh(resource)
    
    return resource


def quick_save_chart(session: SessionDep, user: CurrentUser, chart_data_str: str, dashboard_id: str = None):
    """一键保存图表到仪表板"""
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)

    try:
        chart_data = json.loads(chart_data_str)
    except json.JSONDecodeError:
        raise ValueError("Invalid chart data JSON")

    if dashboard_id:
    # 保存到指定洞察
        dashboard = session.query(CoreDashboard).filter(
            and_(
                CoreDashboard.id == dashboard_id,
                CoreDashboard.workspace_id == oid,
                CoreDashboard.create_by == uid
            )
        ).first()
        if not dashboard:
            raise ValueError("Dashboard not found")
    else:
        # 用用户提问作为默认名称，回退到图表标题
        question = chart_data.get("propValue", {}).get("question", "")
        chart_title = chart_data.get("propValue", {}).get("title", "")
        default_name = question if question else (chart_title if chart_title else _dash_trans(user)('i18n_dashboard.default_name'))

        # 查找或创建默认洞察
        dashboard = session.query(CoreDashboard).filter(
            and_(
                CoreDashboard.workspace_id == oid,
                CoreDashboard.create_by == uid,
                CoreDashboard.name == default_name,
                CoreDashboard.node_type == "leaf"
            )
        ).first()

        if not dashboard:
            dashboard = CoreDashboard()
            dashboard.id = uuid.uuid4().hex
            dashboard.name = default_name
            dashboard.pid = "root"
            dashboard.workspace_id = oid
            dashboard.create_by = uid
            dashboard.create_time = int(time.time())
            dashboard.node_type = "leaf"
            dashboard.type = "dashboard"
            dashboard.canvas_style_data = json.dumps({
                "width": 1920, "height": 1080, "scale": 100,
                "color": "#0f0a1a", "opacity": 1, "background": "#0f0a1a"
            })
            dashboard.component_data = json.dumps([])
            dashboard.canvas_view_info = json.dumps({})
            session.add(dashboard)
            session.flush()

    # 追加图表到 component_data
    try:
        components = json.loads(dashboard.component_data or "[]")
    except json.JSONDecodeError:
        components = []

    # 限制单个仪表板的图表数量，防止 component_data 无限增长
    MAX_CHARTS_PER_DASHBOARD = 50
    if len(components) >= MAX_CHARTS_PER_DASHBOARD:
        raise ValueError(_dash_trans(user)('i18n_dashboard.chart_limit', limit=MAX_CHARTS_PER_DASHBOARD))

    # 自动计算网格位置
    col_count = 2
    idx = len(components)
    col = idx % col_count
    row = idx // col_count
    chart_data["style"] = {
        "left": col * 620 + 20,
        "top": row * 440 + 20,
        "width": 600,
        "height": 400,
        "rotate": 0
    }

    components.append(chart_data)
    dashboard.component_data = json.dumps(components)
    dashboard.update_by = uid
    dashboard.update_time = int(time.time())
    session.add(dashboard)
    session.commit()

    return {"id": dashboard.id, "name": dashboard.name, "chart_count": len(components)}


async def generate_dashboard_summary(session: SessionDep, user: CurrentUser, dashboard_id: str):
    """生成 AI 摘要（带缓存，避免重复消耗 Token）"""
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)

    dashboard = session.query(CoreDashboard).filter(
        and_(
            CoreDashboard.id == dashboard_id,
            CoreDashboard.workspace_id == oid,
            CoreDashboard.create_by == uid
        )
    ).first()

    if not dashboard:
        raise ValueError("Dashboard not found")

    try:
        components = json.loads(dashboard.component_data or "[]")
    except json.JSONDecodeError:
        components = []

    if not components:
        return {"summary": "", "chart_count": 0, "cached": False}

    # 检查缓存：如果已有摘要且 component_data 未变化（通过 update_time 判断）
    if dashboard.ai_summary and dashboard.summary_updated_at:
        dashboard_update_time = dashboard.update_time or 0
        if dashboard.summary_updated_at >= dashboard_update_time:
            return {
                "summary": dashboard.ai_summary,
                "chart_count": len(components),
                "cached": True
            }

    # 构建摘要上下文
    chart_summaries = []
    for comp in components:
        pv = comp.get("propValue", {})
        # 清理用户可控的图表标题，防止 Prompt 注入
        _t = _dash_trans(user)
        title = str(pv.get("title", _t('i18n_dashboard.untitled')))[:50].replace('\n', ' ').replace('\r', '')
        chart_type = str(pv.get("chartType", "unknown"))[:20]
        data = pv.get("data", [])
        data_count = len(data) if isinstance(data, list) else 0
        chart_summaries.append(f"- {title} ({chart_type}): {_t('i18n_dashboard.data_count', count=data_count)}")

    # 尝试使用 LLM 生成摘要
    try:
        from apps.ai_model.model_factory import get_default_config, LLMFactory
        config = await get_default_config()
        llm_instance = LLMFactory.create_llm(config)
        if llm_instance:
            charts_desc = "\n".join(chart_summaries)
            data_samples = []
            for comp in components[:5]:
                pv = comp.get("propValue", {})
                data = pv.get("data", [])
                if isinstance(data, list) and len(data) > 0:
                    sample = data[:3]
                    # 限制数据样本长度，防止超长输入导致 Token 浪费
                    sample_str = json.dumps(sample, ensure_ascii=False, default=str)[:200]
                    title = str(pv.get('title', 'Chart'))[:30]
                    data_samples.append(f"{title}: {sample_str}")

            _t = _dash_trans(user)
            prompt = f"""{_t('i18n_dashboard.summary_prompt')}"""

            from langchain.schema import HumanMessage
            result = llm_instance.llm.invoke([HumanMessage(content=prompt)])
            summary_text = result.content if hasattr(result, 'content') else str(result)

            # 保存摘要到数据库缓存
            dashboard.ai_summary = summary_text
            dashboard.summary_updated_at = int(time.time())
            session.add(dashboard)
            session.commit()

            return {"summary": summary_text, "chart_count": len(components), "cached": False}
    except Exception as e:
        logger.warning(f"LLM summary generation failed: {e}")

    # Fallback: 生成基础统计摘要
    _t = _dash_trans(user)
    chart_types = {}
    for comp in components:
        ct = comp.get("propValue", {}).get("chartType", "other")
        chart_types[ct] = chart_types.get(ct, 0) + 1
    type_desc = "、".join([f"{v}x{k}" for k, v in chart_types.items()])
    summary = _t('i18n_dashboard.fallback_summary', count=len(components), types=type_desc)

    # 缓存 fallback 摘要
    dashboard.ai_summary = summary
    dashboard.summary_updated_at = int(time.time())
    session.add(dashboard)
    session.commit()

    return {"summary": summary, "chart_count": len(components), "cached": False}


async def refresh_all_charts(session: SessionDep, user: CurrentUser, dashboard_id: str):
    """刷新所有图表的数据"""
    oid = str(user.oid if user.oid is not None else 1)
    uid = str(user.id)

    dashboard = session.query(CoreDashboard).filter(
        and_(
            CoreDashboard.id == dashboard_id,
            CoreDashboard.workspace_id == oid,
            CoreDashboard.create_by == uid
        )
    ).first()

    if not dashboard:
        raise ValueError("Dashboard not found")

    try:
        components = json.loads(dashboard.component_data or "[]")
    except json.JSONDecodeError:
        return {"refreshed": 0, "failed": 0, "total": 0}

    refreshed = 0
    failed = 0

    for comp in components:
        record_id = comp.get("propValue", {}).get("recordId")
        if not record_id:
            continue
        try:
            from apps.chat.crud.chat import get_chat_chart_data
            # recordId 来自 JSON 可能是字符串，确保转为 int
            result = get_chat_chart_data(chat_record_id=int(record_id), session=session)
            if result and isinstance(result, dict) and "data" in result:
                comp["propValue"]["data"] = result["data"]
                # 刷新时同步更新 fields 元数据
                if "fields" in result:
                    comp["propValue"]["fields"] = result["fields"]
                refreshed += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"Failed to refresh chart {record_id}: {e}")
            failed += 1

    # 保存更新后的数据
    dashboard.component_data = json.dumps(components)
    dashboard.update_by = uid
    dashboard.update_time = int(time.time())
    session.add(dashboard)
    session.commit()

    return {"refreshed": refreshed, "failed": failed, "total": len(components)}
