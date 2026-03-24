"""ChatBI 权限模块"""

import json
from typing import Optional, List, Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlmodel import SQLModel, Field


class DsRules(SQLModel, table=True):
    """数据源规则模型"""
    __tablename__ = "ds_rules"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    enable: bool = Field(default=True)
    name: str = Field(default="")
    description: Optional[str] = Field(default=None)
    permission_list: Optional[str] = Field(default="[]")  # JSON 字符串
    user_list: Optional[str] = Field(default="[]")  # JSON 字符串
    white_list_user: Optional[str] = Field(default=None)
    create_time: Optional[datetime] = Field(default=None)
    oid: Optional[int] = Field(default=1)


class DsPermission(SQLModel, table=True):
    """数据源权限模型"""
    __tablename__ = "ds_permission"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    enable: bool = Field(default=True)
    name: Optional[str] = Field(default="")
    auth_target_type: Optional[str] = Field(default=None)
    auth_target_id: Optional[int] = Field(default=None)
    type: str = Field(default="row")  # row 或 column
    ds_id: Optional[int] = Field(default=None)
    table_id: Optional[int] = Field(default=0)
    expression_tree: Optional[str] = Field(default=None)
    permissions: Optional[str] = Field(default="[]")  # JSON 字符串
    white_list_user: Optional[str] = Field(default=None)
    create_time: Optional[datetime] = Field(default=None)
    oid: Optional[int] = Field(default=1)  # 工作空间ID


class PermissionDTO(BaseModel):
    """权限数据传输对象"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    table_id: int = 0
    table_name: Optional[str] = None
    type: str = "row"
    permissions: List[Any] = []
    filter_tree: Optional[Any] = None
    oid: int = 1


def transRecord2DTO(session, permission: DsPermission) -> PermissionDTO:
    """将权限记录转换为DTO"""
    from apps.datasource.models.datasource import CoreTable
    
    dto = PermissionDTO(
        id=permission.id,
        name=permission.name or "",
        table_id=permission.table_id or 0,
        type=permission.type,
    )
    
    # 解析 permissions JSON
    try:
        dto.permissions = json.loads(permission.permissions) if permission.permissions else []
    except (json.JSONDecodeError, TypeError):
        dto.permissions = []
    
    # 解析 expression_tree 作为 filter_tree
    try:
        dto.filter_tree = json.loads(permission.expression_tree) if permission.expression_tree else None
    except (json.JSONDecodeError, TypeError):
        dto.filter_tree = None
    
    # 获取表名
    if permission.table_id:
        table = session.get(CoreTable, permission.table_id)
        if table:
            dto.table_name = table.table_name
    
    return dto


# 导出
__all__ = ['DsRules', 'DsPermission', 'PermissionDTO', 'transRecord2DTO']
