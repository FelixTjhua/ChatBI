from fastapi import APIRouter, HTTPException
from sqlmodel import select    
from apps.settings.models.setting_models import term_model
from apps.settings.schemas.setting_schemas import term_schema_creator
from common.core.deps import CurrentUser, SessionDep
from common.core.pagination import Paginator
from common.core.schemas import PaginatedResponse, PaginationParams
router = APIRouter(tags=["Settings"], prefix="/settings/terminology")


@router.get("/pager/{pageNum}/{pageSize}", response_model=PaginatedResponse[term_model])
async def pager(
    session: SessionDep,
    pageNum: int,
    pageSize: int
):
    pagination = PaginationParams(page=pageNum, size=pageSize)
    paginator = Paginator(session)
    filters = {}
    return await paginator.get_paginated_response(
        stmt=term_model,
        pagination=pagination,
        **filters)
    

@router.get("/{id}", response_model=term_model)
async def get_terminology_by_id(
    session: SessionDep,
    id: int
):
    term = session.get(term_model, id)
    if not term:
        raise HTTPException(status_code=404, detail=f"Terminology with id {id} not found")
    return term
    
@router.post("", response_model=term_model)
async def add_terminology(
    session: SessionDep,
    creator: term_schema_creator,
    current_user: CurrentUser
):
    # 添加管理员权限检查，术语库管理属于系统管理功能
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can add terminology")
    terminology = term_model(**creator.model_dump())
    session.add(terminology)
    session.commit()
    return terminology

@router.put("", response_model=term_model)
async def update_terminology(
    session: SessionDep,
    terminology: term_model,
    current_user: CurrentUser
):
    # 添加管理员权限检查
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can update terminology")
    terminology.id = int(terminology.id)
    term = session.exec(select(term_model).where(term_model.id == terminology.id)).first()
    if not term:
        raise HTTPException(status_code=404, detail=f"Terminology with id {terminology.id} not found")
    update_data = terminology.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(term, field, value)
    session.add(term)
    session.commit()
    return terminology

@router.delete("/{id}", response_model=term_model)
async def delete_terminology(
    session: SessionDep,
    id: int,
    current_user: CurrentUser
):
    # 添加管理员权限检查
    if not current_user.isAdmin:
        raise HTTPException(status_code=403, detail="Only admin can delete terminology")
    term = session.exec(select(term_model).where(term_model.id == id)).first()
    if not term:
        raise HTTPException(status_code=404, detail=f"Terminology with id {id} not found")
    session.delete(term)
    session.commit()
    return {
        "message": f"Terminology with ID {id} deleted successfully."
    }
