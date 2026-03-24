"""
审计日志 API
提供审计日志的查询接口
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from common.audit.crud.audit_service import query_audit_logs
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import ChatBILogUtil

router = APIRouter(tags=["audit"], prefix="/audit")


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    create_time: Optional[datetime] = None


class AuditLogPageResponse(BaseModel):
    total: int = 0
    items: List[AuditLogResponse] = []
    page: int = 1
    page_size: int = 20


@router.get("/logs", response_model=AuditLogPageResponse)
async def get_audit_logs(
    session: SessionDep,
    current_user: CurrentUser,
    user_id: Optional[int] = Query(None, description="筛选用户ID"),
    action: Optional[str] = Query(None, description="筛选操作类型"),
    resource_type: Optional[str] = Query(None, description="筛选资源类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    查询审计日志（分页）
    
    支持按用户、操作类型、资源类型筛选
    """
    oid = current_user.oid if current_user.oid else 1
    
    result = query_audit_logs(
        session=session,
        oid=oid,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        page=page,
        page_size=page_size
    )
    
    return AuditLogPageResponse(
        total=result['total'],
        items=[AuditLogResponse.model_validate(item) for item in result['items']],
        page=result['page'],
        page_size=result['page_size']
    )
