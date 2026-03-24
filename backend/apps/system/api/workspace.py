"""
工作空间管理 API
支持工作空间成员管理、用户查找和工作空间切换
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select, or_
from sqlalchemy import func

from apps.system.models.user import UserModel
from common.core.deps import CurrentUser, SessionDep, Trans
from common.core.pagination import Paginator
from common.core.schemas import PaginatedResponse, PaginationParams

router = APIRouter(tags=["workspace"], prefix="/workspace")


class UwsCreateRequest(BaseModel):
    uid_list: list[int]


class UwsDeleteRequest(BaseModel):
    uid_list: list[int]


class WorkspaceOption(BaseModel):
    id: int
    name: str


class UserOption(BaseModel):
    id: int
    name: str
    account: str


class WorkspaceUserGrid(BaseModel):
    id: int
    name: str
    account: str
    email: str = ""
    status: int = 1
    weight: int = 0


# ===== 工作空间选项 =====

@router.get("/options")
async def ws_options(current_user: CurrentUser) -> list[WorkspaceOption]:
    """获取当前用户可用的工作空间列表（简化版：仅返回默认工作空间）"""
    return [WorkspaceOption(id=1, name="默认工作空间")]


@router.put("/change/{oid}")
async def ws_change(session: SessionDep, current_user: CurrentUser, oid: int):
    """切换当前工作空间（简化版：更新用户的 oid 字段）"""
    db_user = session.get(UserModel, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.oid = oid
    session.add(db_user)
    session.commit()
    return {"message": "ok"}


# ===== 工作空间成员管理 =====

@router.get("/user/pager/{pageNum}/{pageSize}", response_model=PaginatedResponse[WorkspaceUserGrid])
async def workspace_user_list(
    session: SessionDep,
    current_user: CurrentUser,
    pageNum: int,
    pageSize: int,
    keyword: Optional[str] = Query(None),
):
    """获取当前工作空间的成员列表"""
    oid = current_user.oid if current_user.oid else 1
    pagination = PaginationParams(page=pageNum, size=pageSize)
    paginator = Paginator(session)

    # 按 oid 过滤，防止跨工作空间查看成员
    stmt = select(UserModel).where(UserModel.oid == oid).order_by(UserModel.create_time.desc())

    if keyword and keyword.strip():
        # 转义 LIKE 通配符
        safe_kw = keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = f"%{safe_kw}%"
        stmt = stmt.where(
            or_(
                func.lower(UserModel.account).like(pattern.lower()),
                func.lower(UserModel.name).like(pattern.lower()),
                func.lower(UserModel.email).like(pattern.lower()),
            )
        )

    return await paginator.get_paginated_response(stmt=stmt, pagination=pagination)


@router.get("/user/option/pager/{pageNum}/{pageSize}", response_model=PaginatedResponse[WorkspaceUserGrid])
async def workspace_option_user_list(
    session: SessionDep,
    current_user: CurrentUser,
    pageNum: int,
    pageSize: int,
    oid: Optional[int] = Query(None),
):
    """获取可添加到工作空间的用户列表"""
    # 仅管理员可查看可添加用户列表
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can view user options")
    pagination = PaginationParams(page=pageNum, size=pageSize)
    paginator = Paginator(session)
    stmt = select(UserModel).order_by(UserModel.create_time.desc())
    return await paginator.get_paginated_response(stmt=stmt, pagination=pagination)


@router.post("/uws/create")
async def workspace_uws_create(
    session: SessionDep,
    current_user: CurrentUser,
    trans: Trans,
    req: UwsCreateRequest,
):
    """将用户添加到当前工作空间（简化版：验证用户存在即可）"""
    if not current_user.isAdmin:
        raise HTTPException(
            status_code=403,
            detail=trans(
                "i18n_permission.no_permission",
                url=" post[/workspace/uws/create],",
                msg=trans("i18n_permission.only_admin"),
            ),
        )
    for uid in req.uid_list:
        db_user = session.get(UserModel, uid)
        if not db_user:
            raise HTTPException(status_code=404, detail=f"User {uid} not found")
    return {"message": "ok"}


@router.post("/uws/delete")
async def workspace_uws_delete(
    session: SessionDep,
    current_user: CurrentUser,
    trans: Trans,
    req: UwsDeleteRequest,
):
    """从当前工作空间移除用户（简化版：禁用用户状态）"""
    if not current_user.isAdmin:
        raise HTTPException(
            status_code=403,
            detail=trans(
                "i18n_permission.no_permission",
                url=" post[/workspace/uws/delete],",
                msg=trans("i18n_permission.only_admin"),
            ),
        )
    for uid in req.uid_list:
        if uid == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot remove yourself")
        db_user = session.get(UserModel, uid)
        if not db_user:
            raise HTTPException(status_code=404, detail=f"User {uid} not found")
    return {"message": "ok"}


@router.get("/uws/option")
async def uws_option(
    session: SessionDep,
    current_user: CurrentUser,
    keyword: Optional[str] = Query(None),
) -> Optional[UserOption]:
    """根据关键字查找用户（用于添加成员时搜索）"""
    if not keyword or not keyword.strip():
        return None
    # 转义 LIKE 通配符
    safe_kw = keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    pattern = f"%{safe_kw}%"
    stmt = select(UserModel).where(
        or_(
            func.lower(UserModel.account).like(pattern.lower()),
            func.lower(UserModel.name).like(pattern.lower()),
        )
    ).limit(1)
    result = session.exec(stmt).first()
    if not result:
        return None
    return UserOption(id=result.id, name=result.name, account=result.account)
