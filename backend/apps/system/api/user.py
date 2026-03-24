from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, Query
from sqlmodel import SQLModel, or_, select, delete as sqlmodel_delete
from sqlalchemy import func
from apps.system.crud.user import check_account_exists, check_email_exists, check_email_format, check_pwd_format, get_db_user, single_delete
from apps.system.models.user import UserModel
from apps.system.schemas.auth import CacheName, CacheNamespace
from apps.system.schemas.system_schema import PwdEditor, UserCreator, UserEditor, UserGrid, UserLanguage, UserStatus
from common.core.deps import CurrentUser, SessionDep, Trans
from common.core.pagination import Paginator
from common.core.schemas import PaginatedResponse, PaginationParams
from common.core.security import default_hashed_pwd, hash_password, verify_pwd
from common.core.chatbi_cache import clear_cache
from common.core.config import settings

router = APIRouter(tags=["user"], prefix="/user")

from fastapi import HTTPException

@router.get("/info")
async def user_info(current_user: CurrentUser):
    return current_user

@router.get("/defaultPwd")
async def default_pwd(current_user: CurrentUser, trans: Trans) -> str:
    """获取默认密码 - 仅管理员可访问"""
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " get[/user/defaultPwd],", msg = trans('i18n_permission.only_admin')))
    return settings.DEFAULT_PWD

@router.get("/pager/{pageNum}/{pageSize}", response_model=PaginatedResponse[UserGrid])
async def pager(
    session: SessionDep,
    current_user: CurrentUser,
    trans: Trans,
    pageNum: int,
    pageSize: int,
    keyword: Optional[str] = Query(None, description="搜索关键字(可选)"),
    status: Optional[int] = Query(None, description="状态"),
    role: Optional[list[str]] = Query(None, description="成员类型"),
):
    # 用户列表仅管理员可访问，防止普通用户枚举所有用户信息
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url=" get[/user/pager],", msg=trans('i18n_permission.only_admin')))
    pagination = PaginationParams(page=pageNum, size=pageSize)
    paginator = Paginator(session)
    
    # 构建查询语句
    origin_stmt = (
        select(UserModel)
        .order_by(UserModel.create_time.desc())
    )
    
    # 应用状态筛选
    if status is not None:
        origin_stmt = origin_stmt.where(UserModel.status == status)
    
    # 应用角色筛选
    if role and len(role) > 0:
        origin_stmt = origin_stmt.where(UserModel.role.in_(role))
    
    # 应用关键字搜索
    if keyword and keyword.strip() and keyword.lower() != 'none':
        # 转义 LIKE 通配符，防止用户输入 % 或 _ 改变查询语义
        safe_keyword = keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        keyword_pattern = f"%{safe_keyword}%"
        
        from sqlalchemy import func
        origin_stmt = origin_stmt.where(
            or_(
                func.lower(UserModel.account).like(keyword_pattern.lower()),
                func.lower(UserModel.name).like(keyword_pattern.lower()),
                func.lower(UserModel.email).like(keyword_pattern.lower())
            )
        )
    
    # 获取分页结果
    user_page = await paginator.get_paginated_response(
        stmt=origin_stmt,
        pagination=pagination
    )
    
    return user_page

@router.get("/{id}", response_model=UserEditor)
async def query(session: SessionDep, current_user: CurrentUser, trans: Trans, id: int) -> UserEditor:
    # 仅管理员或用户本人可查看用户详情
    if not current_user.isAdmin and current_user.id != id:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url=" get[/user/{id}],", msg=trans('i18n_permission.only_admin')))
    db_user: UserModel = get_db_user(session = session, user_id = id)
    result = UserEditor.model_validate(db_user.model_dump())
    return result

@router.post("")
async def create(session: SessionDep, current_user: CurrentUser, creator: UserCreator, trans: Trans):
    # 只有管理员可以创建用户
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " post[/user],", msg = trans('i18n_permission.only_admin')))
    
    if check_account_exists(session=session, account=creator.account):
        raise HTTPException(status_code=400, detail=trans('i18n_exist', msg = f"{trans('i18n_user.account')} [{creator.account}]"))
    if check_email_exists(session=session, email=creator.email):
        raise HTTPException(status_code=400, detail=trans('i18n_exist', msg = f"{trans('i18n_user.email')} [{creator.email}]"))
    if not check_email_format(creator.email):
        raise HTTPException(status_code=400, detail=trans('i18n_format_invalid', key = f"{trans('i18n_user.email')} [{creator.email}]"))
    
    # 验证role字段
    if creator.role not in ['admin', 'member']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'member'")
    
    data = creator.model_dump(exclude_unset=True)
    user_model = UserModel.model_validate(data)
    user_model.language = "zh-CN"
    user_model.password = default_hashed_pwd()
    session.add(user_model)
    session.commit()
    
@router.put("")
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="editor.id")
async def update(session: SessionDep, current_user: CurrentUser, editor: UserEditor, trans: Trans):
    # 只有管理员可以编辑用户
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " put[/user],", msg = trans('i18n_permission.only_admin')))
    
    user_model: UserModel = get_db_user(session = session, user_id = editor.id)
    if not user_model:
        raise HTTPException(status_code=404, detail=f"User with id [{editor.id}] not found!")
    if editor.account != user_model.account:
        raise HTTPException(status_code=400, detail="account cannot be changed!")
    if editor.email != user_model.email and check_email_exists(session=session, email=editor.email):
        raise HTTPException(status_code=400, detail=trans('i18n_exist', msg = f"{trans('i18n_user.email')} [{editor.email}]"))
    if not check_email_format(editor.email):
        raise HTTPException(status_code=400, detail=trans('i18n_format_invalid', key = f"{trans('i18n_user.email')} [{editor.email}]"))
    
    # 验证role字段
    if editor.role not in ['admin', 'member']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'member'")
    
    data = editor.model_dump(exclude_unset=True)
    user_model.sqlmodel_update(data)
    
    session.add(user_model)
    session.commit()
    
@router.delete("/{id}")
async def delete(session: SessionDep, current_user: CurrentUser, trans: Trans, id: int):
    # 只有管理员可以删除用户
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " delete[/user/{id}],", msg = trans('i18n_permission.only_admin')))
    
    # 不能删除自己
    if id == current_user.id:
        raise HTTPException(status_code=400, detail=trans('i18n_user.cannot_delete_self'))
    
    # 检查用户是否存在
    db_user: UserModel = get_db_user(session=session, user_id=id)
    if not db_user:
        raise HTTPException(status_code=404, detail=f"User with id [{id}] not found!")
    
    await single_delete(session, id)

@router.delete("")    
async def batch_del(session: SessionDep, current_user: CurrentUser, trans: Trans, id_list: list[int]):
    # 只有管理员可以批量删除用户
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " delete[/user],", msg = trans('i18n_permission.only_admin')))
    
    # 批量删除数量限制
    MAX_BATCH_DELETE = 50
    if len(id_list) > MAX_BATCH_DELETE:
        raise HTTPException(status_code=400, detail=trans('i18n_user.batch_delete_limit', limit=MAX_BATCH_DELETE))
    
    # 不能删除自己
    if current_user.id in id_list:
        raise HTTPException(status_code=400, detail=trans('i18n_user.cannot_delete_self'))
    
    for id in id_list:
        await single_delete(session, id)
    
@router.put("/language")
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="current_user.id")
async def langChange(session: SessionDep, current_user: CurrentUser, trans: Trans, language: UserLanguage):
    lang = language.language
    if lang not in ["zh-CN", "en"]:
        raise HTTPException(status_code=400, detail=trans('i18n_user.language_not_support', key = lang))
    db_user: UserModel = get_db_user(session=session, user_id=current_user.id)
    db_user.language = lang
    session.add(db_user)
    session.commit()
    
@router.patch("/pwd/{id}")
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="id")
async def pwdReset(session: SessionDep, current_user: CurrentUser, trans: Trans, id: int):
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = " patch[/user/pwd/id],", msg = trans('i18n_permission.only_admin')))
    db_user: UserModel = get_db_user(session=session, user_id=id)
    if not db_user:
        raise HTTPException(status_code=404, detail=f"User with id [{id}] not found!")
    db_user.password = default_hashed_pwd()
    session.add(db_user)
    session.commit()

@router.put("/pwd")
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="current_user.id")
async def pwdUpdate(session: SessionDep, current_user: CurrentUser, trans: Trans, editor: PwdEditor):
    new_pwd = editor.new_pwd
    if not check_pwd_format(new_pwd):
        raise HTTPException(status_code=400, detail=trans('i18n_format_invalid', key = trans('i18n_user.password')))
    db_user: UserModel = get_db_user(session=session, user_id=current_user.id)
    if not verify_pwd(editor.pwd, db_user.password):
        raise HTTPException(status_code=400, detail=trans('i18n_error', key = trans('i18n_user.password')))
    db_user.password = hash_password(new_pwd)
    session.add(db_user)
    session.commit()
    
@router.patch("/status")
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="statusDto.id")
async def statusChange(session: SessionDep, current_user: CurrentUser, trans: Trans, statusDto: UserStatus):
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail=trans('i18n_permission.no_permission', url = ", ", msg = trans('i18n_permission.only_admin')))
    status = statusDto.status
    if status not in [0, 1]:
        return {"message": "status not supported"}
    db_user: UserModel = get_db_user(session=session, user_id=statusDto.id)
    if not db_user:
        raise HTTPException(status_code=404, detail=f"User with id [{statusDto.id}] not found!")
    db_user.status = status
    session.add(db_user)
    session.commit()