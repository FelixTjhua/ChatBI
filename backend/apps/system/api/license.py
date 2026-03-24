"""
ChatBI License API
Copyright © 2026 ChatBI
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from common.chatbi.license import ChatBILicenseUtil

router = APIRouter(tags=["system/license"], prefix="/system/license")


class LicenseInfo(BaseModel):
    """License 信息模型"""
    status: str = "valid"
    corporation: str = ""
    expired: str = ""
    count: int = 0
    version: str = ""
    edition: str = ""
    serialNo: str = ""
    remark: str = ""
    isv: str = ""


class LicenseResponse(BaseModel):
    """License 响应模型"""
    status: str = "valid"
    license: Optional[LicenseInfo] = None
    message: Optional[str] = None


class LicenseUpdateRequest(BaseModel):
    """License 更新请求"""
    license_key: str


@router.get("", response_model=LicenseResponse)
async def validate_license():
    """
    验证 License
    
    对于学术版/社区版，始终返回有效状态
    """
    info = ChatBILicenseUtil.get_license_info()
    
    return LicenseResponse(
        status="valid",
        license=LicenseInfo(
            status="valid",
            corporation=info.get("corporation", "ChatBI"),
            expired=info.get("expired", "永久"),
            count=info.get("count", 999),
            version=info.get("version", "1.0.0"),
            edition=info.get("edition", "Academic"),
            serialNo=info.get("serialNo", "CHATBI-ACADEMIC-2026"),
            remark=info.get("remark", "毕业论文项目 - 基于RAG与大语言模型的商业智能分析对话系统"),
            isv=info.get("isv", "ChatBI"),
        )
    )


@router.get("/version")
async def get_version():
    """获取版本信息"""
    return {
        "version": "1.0.0",
        "name": "ChatBI",
        "edition": "Academic"
    }


@router.post("", response_model=LicenseResponse)
async def update_license(data: LicenseUpdateRequest):
    """
    更新 License
    
    对于学术版，此接口仅返回成功状态
    """
    # 学术版不需要真正更新 license
    info = ChatBILicenseUtil.get_license_info()
    
    return LicenseResponse(
        status="valid",
        license=LicenseInfo(
            status="valid",
            corporation=info.get("corporation", "ChatBI"),
            expired=info.get("expired", "永久"),
            count=info.get("count", 999),
            version=info.get("version", "1.0.0"),
            edition=info.get("edition", "Academic"),
            serialNo=info.get("serialNo", "CHATBI-ACADEMIC-2026"),
            remark=info.get("remark", "毕业论文项目 - 基于RAG与大语言模型的商业智能分析对话系统"),
            isv=info.get("isv", "ChatBI"),
        ),
        message="License 更新成功"
    )
