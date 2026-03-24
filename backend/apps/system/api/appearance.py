"""
ChatBI 外观设置 API
Copyright © 2026 ChatBI
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/system/appearance", tags=["appearance"])


class AppearanceUI(BaseModel):
    """外观设置响应模型"""
    name: str = "ChatBI"
    slogan: str = "基于RAG与大语言模型的商业智能分析对话系统"
    themeColor: str = "default"
    showSlogan: bool = True
    loginBg: Optional[str] = None
    loginImage: Optional[str] = None
    logo: Optional[str] = None
    icon: Optional[str] = None


@router.get("/ui")
async def get_appearance_ui() -> AppearanceUI:
    """获取外观设置"""
    return AppearanceUI()


@router.get("/picture/{picture_type}")
async def get_appearance_picture(picture_type: str):
    """获取外观图片"""
    return None
