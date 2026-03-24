from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import io
import logging

import pandas as pd

from apps.dashboard.crud.dashboard_service import list_resource, load_resource, \
    create_resource, create_canvas, validate_name, delete_resource, update_resource, update_canvas
from apps.dashboard.models.dashboard_model import CreateDashboard, BaseDashboard, QueryDashboard, DashboardResponse
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"], prefix="/dashboard")


@router.post("/list_resource")
async def list_resource_api(session: SessionDep, dashboard: QueryDashboard, current_user: CurrentUser):
    return list_resource(session=session, dashboard=dashboard, current_user=current_user)


@router.post("/load_resource")
async def load_resource_api(session: SessionDep, dashboard: QueryDashboard, current_user: CurrentUser):
    return load_resource(session=session, dashboard=dashboard, current_user=current_user)


@router.post("/create_resource", response_model=BaseDashboard)
async def create_resource_api(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    return create_resource(session, user, dashboard)


@router.post("/update_resource", response_model=BaseDashboard)
async def update_resource_api(session: SessionDep, user: CurrentUser, dashboard: QueryDashboard):
    return update_resource(session=session, user=user, dashboard=dashboard)


@router.delete("/delete_resource/{resource_id}")
async def delete_resource_api(session: SessionDep, resource_id: str, user: CurrentUser):
    """删除资源（需要验证所有权）"""
    return delete_resource(session, resource_id, user)


@router.post("/create_canvas", response_model=BaseDashboard)
async def create_canvas_api(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    return create_canvas(session, user, dashboard)


@router.post("/update_canvas", response_model=BaseDashboard)
async def update_canvas_api(session: SessionDep, user: CurrentUser, dashboard: CreateDashboard):
    return update_canvas(session, user, dashboard)


@router.post("/check_name")
async def check_name_api(session: SessionDep, user: CurrentUser, dashboard: QueryDashboard):
    return validate_name(session, user, dashboard)


@router.post("/move_resource")
async def move_resource_api(session: SessionDep, user: CurrentUser, dashboard: QueryDashboard):
    """移动资源到新的父节点"""
    from apps.dashboard.crud.dashboard_service import move_resource
    return move_resource(session, user, dashboard)


class QuickSaveRequest(BaseModel):
    chart_data: str  # JSON string of chart component
    dashboard_id: Optional[str] = None  # If None, use/create default dashboard


@router.post("/quick_save")
async def quick_save_api(session: SessionDep, user: CurrentUser, req: QuickSaveRequest):
    """一键保存图表到仪表板"""
    from apps.dashboard.crud.dashboard_service import quick_save_chart
    return quick_save_chart(session, user, req.chart_data, req.dashboard_id)


class SummaryRequest(BaseModel):
    dashboard_id: str


@router.post("/generate_summary")
async def generate_summary_api(session: SessionDep, user: CurrentUser, req: SummaryRequest):
    """生成 AI 摘要"""
    from apps.dashboard.crud.dashboard_service import generate_dashboard_summary
    return await generate_dashboard_summary(session, user, req.dashboard_id)


@router.post("/refresh_all_charts")
async def refresh_all_charts_api(session: SessionDep, user: CurrentUser, req: SummaryRequest):
    """刷新所有图表的数据"""
    from apps.dashboard.crud.dashboard_service import refresh_all_charts
    return await refresh_all_charts(session, user, req.dashboard_id)


@router.get("/{dashboard_id}/excel/export")
async def export_dashboard_excel(session: SessionDep, user: CurrentUser, dashboard_id: str):
    """导出洞察中所有卡片数据为 Excel（多 Sheet）"""
    import asyncio
    from apps.dashboard.models.dashboard_model import CoreDashboard

    dashboard = session.get(CoreDashboard, dashboard_id)
    # Excel 导出需同时验证 workspace_id + create_by，与其他端点一致，防止越权导出
    oid = str(user.oid if user.oid is not None else 1)
    if not dashboard or dashboard.create_by != str(user.id) or dashboard.workspace_id != oid:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    components = []
    if dashboard.component_data:
        try:
            components = json.loads(dashboard.component_data)
        except Exception as e:
            ChatBILogUtil.warning(f"Failed to parse dashboard component_data for id={dashboard_id}: {e}")

    if not components:
        raise HTTPException(status_code=400, detail="No data to export")

    def inner():
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter',
                            engine_kwargs={'options': {'strings_to_numbers': False}}) as writer:
            sheet_idx = 0
            for comp in components:
                pv = comp.get('propValue', {})
                card_type = pv.get('cardType', 'chart')
                title = pv.get('title', f'Sheet{sheet_idx + 1}')
                # 清理 sheet 名称（Excel 限制 31 字符，不能含特殊字符）
                safe_sheet = title[:31].replace('/', '-').replace('\\', '-').replace('*', '').replace('?', '').replace('[', '').replace(']', '').replace(':', '-')
                if not safe_sheet.strip():
                    safe_sheet = f'Sheet{sheet_idx + 1}'
                # 避免重名
                existing = [s for s in writer.sheets]
                if safe_sheet in existing:
                    safe_sheet = f'{safe_sheet}_{sheet_idx}'

                data = pv.get('data', [])
                if card_type in ('chart', 'data_table') and data:
                    # 图表/数据表类型：导出数据
                    df = pd.DataFrame(data)
                    # 如果有 fields 定义，用 fields 作为列名过滤
                    fields = pv.get('fields', [])
                    if fields:
                        cols = [f for f in fields if f in df.columns]
                        if cols:
                            df = df[cols]
                    df.to_excel(writer, sheet_name=safe_sheet, index=False)
                    sheet_idx += 1
                elif card_type in ('analysis', 'prediction') and (pv.get('content') or data):
                    # 分析/预测类型：导出文本 + 数据（如果有）
                    rows = []
                    content = pv.get('content', '')
                    if content:
                        rows.append({'内容': content})
                    if data:
                        df_data = pd.DataFrame(data)
                        # 先写文本内容
                        if rows:
                            df_text = pd.DataFrame(rows)
                            df_text.to_excel(writer, sheet_name=safe_sheet, index=False)
                            df_data.to_excel(writer, sheet_name=safe_sheet, index=False,
                                             startrow=len(rows) + 2)
                        else:
                            df_data.to_excel(writer, sheet_name=safe_sheet, index=False)
                    elif rows:
                        pd.DataFrame(rows).to_excel(writer, sheet_name=safe_sheet, index=False)
                    sheet_idx += 1
                elif card_type == 'document_qa' and pv.get('content'):
                    rows = [{'内容': pv.get('content', '')}]
                    sources = pv.get('sources', [])
                    if sources:
                        for src in sources:
                            rows.append({
                                '内容': f"来源: {src.get('source_name', '')} P{src.get('page_number', '')} {src.get('section_title', '')}"
                            })
                    pd.DataFrame(rows).to_excel(writer, sheet_name=safe_sheet, index=False)
                    sheet_idx += 1

            if sheet_idx == 0:
                pd.DataFrame([{'info': 'No data'}]).to_excel(writer, sheet_name='Sheet1', index=False)

        buffer.seek(0)
        return io.BytesIO(buffer.getvalue())

    result = await asyncio.to_thread(inner)
    from urllib.parse import quote
    safe_name = quote(dashboard.name or 'dashboard', safe='')
    return StreamingResponse(
        result,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.xlsx"}
    )
