"""ChatBI License 管理模块"""

from datetime import datetime
from typing import Optional, Dict, Any


class ChatBILicenseUtil:
    """ChatBI License 工具类"""
    
    # License 状态
    _license_info: Optional[Dict[str, Any]] = None
    _is_valid: bool = True  # 默认有效（社区版/学术版）
    
    @classmethod
    def valid(cls) -> bool:
        """
        检查 License 是否有效
        
        对于学术/论文项目，默认返回 True
        """
        return cls._is_valid
    
    @classmethod
    def get_license_info(cls) -> Dict[str, Any]:
        """获取 License 信息"""
        if cls._license_info is None:
            cls._license_info = {
                'status': 'valid',
                'corporation': 'ChatBI',
                'expired': '永久',
                'count': 999,
                'version': '1.0.0',
                'edition': 'Academic',  # 学术版
                'serialNo': 'CHATBI-ACADEMIC-2026',
                'remark': '毕业论文项目 - 基于RAG与大语言模型的商业智能分析对话系统',
                'isv': 'ChatBI',
            }
        return cls._license_info
    
    @classmethod
    def set_valid(cls, is_valid: bool):
        """设置 License 有效性"""
        cls._is_valid = is_valid
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """验证 License"""
        return {
            'status': 'valid' if cls._is_valid else 'invalid',
            'license': cls.get_license_info()
        }


# 兼容旧接口
ChatBILicenseUtil = ChatBILicenseUtil
