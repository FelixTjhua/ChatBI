"""
审计日志辅助工具
提供便捷的审计日志记录方法，用于在关键操作中集成审计功能
"""
import json
from typing import Optional

from sqlmodel import Session

from common.audit.crud.audit_service import create_audit_log
from common.utils.utils import ChatBILogUtil


def log_chat_created(session: Session, user_id: int, user_name: str, chat_id: int,
                     datasource_id: Optional[int] = None, oid: int = 1, ip: str = None):
    """记录对话创建"""
    details = json.dumps({"chat_id": chat_id, "datasource_id": datasource_id}, ensure_ascii=False)
    create_audit_log(session, user_id, user_name, "CREATE_CHAT",
                     resource_type="chat", resource_id=chat_id,
                     details=details, ip_address=ip, oid=oid)


def log_chat_deleted(session: Session, user_id: int, user_name: str, chat_id: int,
                     oid: int = 1, ip: str = None):
    """记录对话删除"""
    create_audit_log(session, user_id, user_name, "DELETE_CHAT",
                     resource_type="chat", resource_id=chat_id,
                     ip_address=ip, oid=oid)


def log_datasource_created(session: Session, user_id: int, user_name: str, ds_id: int,
                           ds_name: str, oid: int = 1, ip: str = None):
    """记录数据源创建"""
    details = json.dumps({"ds_name": ds_name}, ensure_ascii=False)
    create_audit_log(session, user_id, user_name, "CREATE_DATASOURCE",
                     resource_type="datasource", resource_id=ds_id,
                     details=details, ip_address=ip, oid=oid)


def log_datasource_deleted(session: Session, user_id: int, user_name: str, ds_id: int,
                           oid: int = 1, ip: str = None):
    """记录数据源删除"""
    create_audit_log(session, user_id, user_name, "DELETE_DATASOURCE",
                     resource_type="datasource", resource_id=ds_id,
                     ip_address=ip, oid=oid)


def log_file_uploaded(session: Session, user_id: int, user_name: str, filename: str,
                      file_type: str, oid: int = 1, ip: str = None):
    """记录文件上传"""
    details = json.dumps({"filename": filename, "file_type": file_type}, ensure_ascii=False)
    create_audit_log(session, user_id, user_name, "UPLOAD_FILE",
                     resource_type="file", details=details,
                     ip_address=ip, oid=oid)


def log_query_executed(session: Session, user_id: int, user_name: str, chat_id: int,
                       question: str, oid: int = 1, ip: str = None):
    """记录用户查询"""
    # 截断过长的问题
    truncated_q = question[:200] if question else ''
    details = json.dumps({"chat_id": chat_id, "question": truncated_q}, ensure_ascii=False)
    create_audit_log(session, user_id, user_name, "QUERY",
                     resource_type="chat", resource_id=chat_id,
                     details=details, ip_address=ip, oid=oid)
