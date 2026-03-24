"""
审计日志 CRUD 操作
"""
from datetime import datetime
from typing import Optional, List

from sqlmodel import Session, select, col

from common.audit.models.log_model import AuditLog
from common.utils.utils import ChatBILogUtil


def create_audit_log(
    session: Session,
    user_id: int,
    user_name: str,
    action: str,
    resource_type: str = None,
    resource_id: int = None,
    details: str = None,
    ip_address: str = None,
    user_agent: str = None,
    oid: int = 1
) -> AuditLog:
    """创建审计日志记录"""
    try:
        log = AuditLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            oid=oid,
            create_time=datetime.now()
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log
    except Exception as e:
        session.rollback()
        ChatBILogUtil.error(f"Failed to create audit log: {e}")
        return None


def query_audit_logs(
    session: Session,
    oid: int = 1,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20
) -> dict:
    """查询审计日志"""
    try:
        stmt = select(AuditLog).where(AuditLog.oid == oid)
        
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if start_time:
            stmt = stmt.where(AuditLog.create_time >= start_time)
        if end_time:
            stmt = stmt.where(AuditLog.create_time <= end_time)
        
        # 计算总数
        from sqlmodel import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.exec(count_stmt).one()
        
        # 分页查询
        stmt = stmt.order_by(col(AuditLog.create_time).desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = session.exec(stmt).all()
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'page_size': page_size
        }
    except Exception as e:
        ChatBILogUtil.error(f"Failed to query audit logs: {e}")
        return {'total': 0, 'items': [], 'page': page, 'page_size': page_size}
