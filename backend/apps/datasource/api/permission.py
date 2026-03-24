"""
ChatBI 数据源权限 API
Copyright © 2026 ChatBI
"""

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from common.core.deps import SessionDep, CurrentUser, Trans
from common.chatbi.permissions import DsPermission, DsRules
from sqlmodel import select

router = APIRouter(tags=["ds_permission"], prefix="/ds_permission")


class PermissionSaveRequest(BaseModel):
    id: Optional[int] = None
    name: str = ""
    table_id: int
    type: str = "row"  # row 或 column
    permissions: str = "[]"
    filter_tree: Optional[str] = None  # 前端使用 filter_tree，映射到数据库的 expression_tree


@router.post("/list")
async def list_permissions(
    session: SessionDep,
    current_user: CurrentUser
):
    """获取权限列表"""
    try:
        stmt = select(DsPermission).where(DsPermission.oid == current_user.oid)
        permissions = session.exec(stmt).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "table_id": p.table_id,
                "type": p.type,
                "permissions": p.permissions,
                "filter_tree": p.expression_tree,  # 数据库字段是 expression_tree
            }
            for p in permissions
        ]
    except Exception:
        return []


@router.post("/save")
async def save_permission(
    session: SessionDep,
    current_user: CurrentUser,
    trans: Trans,
    data: PermissionSaveRequest
):
    """保存权限"""
    try:
        if data.id:
            # 更新
            permission = session.get(DsPermission, data.id)
            if permission:
                # 验证权限记录属于当前用户的工作空间，防止 IDOR 越权修改
                if permission.oid != current_user.oid:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail=trans('i18n_ds_permission.no_permission'))
                permission.name = data.name
                permission.table_id = data.table_id
                permission.type = data.type
                permission.permissions = data.permissions
                permission.expression_tree = data.filter_tree  # 映射到 expression_tree
                session.add(permission)
                session.commit()
                return {"id": permission.id, "message": trans('i18n_ds_permission.save_success')}
        
        # 创建
        permission = DsPermission(
            name=data.name,
            table_id=data.table_id,
            type=data.type,
            permissions=data.permissions,
            expression_tree=data.filter_tree,  # 映射到 expression_tree
            oid=current_user.oid
        )
        session.add(permission)
        session.commit()
        session.refresh(permission)
        return {"id": permission.id, "message": trans('i18n_ds_permission.create_success')}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"保存权限失败: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=trans('i18n_ds_permission.save_failed'))


@router.post("/delete/{permission_id}")
async def delete_permission(
    session: SessionDep,
    current_user: CurrentUser,
    trans: Trans,
    permission_id: int
):
    """删除权限"""
    try:
        permission = session.get(DsPermission, permission_id)
        if permission:
            # 验证权限记录属于当前用户的工作空间，防止 IDOR 越权删除
            if permission.oid != current_user.oid:
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail=trans('i18n_ds_permission.no_permission'))
            session.delete(permission)
            session.commit()
        return {"message": trans('i18n_ds_permission.delete_success')}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"删除权限失败: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=trans('i18n_ds_permission.delete_failed'))
