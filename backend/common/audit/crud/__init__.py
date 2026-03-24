"""
ChatBI 审计 CRUD 模块
"""
from .audit_service import create_audit_log, query_audit_logs

__all__ = ['create_audit_log', 'query_audit_logs']
