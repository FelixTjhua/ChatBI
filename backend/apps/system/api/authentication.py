"""
ChatBI 认证平台 API
Copyright © 2026 ChatBI
"""

from fastapi import APIRouter

router = APIRouter(tags=["system/authentication"], prefix="/system/authentication")


@router.get("/platform/status")
async def platform_status():
    """
    获取认证平台状态
    
    ChatBI 学术版 - 返回空列表（不启用第三方登录）
    """
    return []


@router.get("/login/{category}")
async def get_login_url(category: int):
    """
    获取第三方登录 URL
    
    ChatBI 学术版 - 不支持第三方登录
    """
    return None
