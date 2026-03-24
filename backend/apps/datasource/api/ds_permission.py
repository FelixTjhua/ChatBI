"""
ChatBI 数据源权限 API
Copyright © 2026 ChatBI
"""
from fastapi import APIRouter
from typing import List, Any

router = APIRouter(prefix="/ds_permission", tags=["ds_permission"])


@router.post("/list")
async def list_permissions() -> List[Any]:
    """获取权限列表 - 学术版返回空列表"""
    return []


@router.post("/save")
async def save_permissions(data: dict) -> dict:
    """保存权限 - 学术版不实现"""
    return {"message": "Permission saved"}


@router.post("/delete/{id}")
async def delete_permission(id: int) -> dict:
    """删除权限 - 学术版不实现"""
    return {"message": f"Permission {id} deleted"}
