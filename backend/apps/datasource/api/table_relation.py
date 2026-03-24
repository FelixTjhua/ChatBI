# Author: Junjun
# Date: 2025/9/24
from typing import List

from fastapi import APIRouter, HTTPException

from apps.datasource.models.datasource import CoreDatasource
from common.core.deps import SessionDep, CurrentUser

router = APIRouter(tags=["table_relation"], prefix="/table_relation")


@router.post("/save/{ds_id}")
async def save_relation(session: SessionDep, user: CurrentUser, ds_id: int, relation: List[dict]):
    ds = session.get(CoreDatasource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Datasource not found")
    # OID 权限验证，防止跨工作空间操作
    if hasattr(ds, 'oid') and ds.oid != user.oid:
        raise HTTPException(status_code=403, detail="No permission")
    ds.table_relation = relation
    session.commit()
    return True


@router.post("/get/{ds_id}")
async def get_relation(session: SessionDep, user: CurrentUser, ds_id: int):
    ds = session.get(CoreDatasource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Datasource not found")
    if hasattr(ds, 'oid') and ds.oid != user.oid:
        raise HTTPException(status_code=403, detail="No permission")
    return ds.table_relation if ds.table_relation else []
