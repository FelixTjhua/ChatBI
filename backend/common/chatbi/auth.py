"""ChatBI 认证模块"""

from typing import Optional, Any
from datetime import datetime

from common.utils.utils import ChatBILogUtil


async def chatbi_logout(session, request, dto) -> Optional[Any]:
    """ChatBI 登出函数"""
    try:
        # 记录登出日志
        user_id = getattr(dto, 'user_id', None) or getattr(dto, 'uid', None)
        origin = getattr(dto, 'origin', 0)
        
        ChatBILogUtil.info(f"用户登出: user_id={user_id}, origin={origin}")
        
        # 如果有 token 黑名单机制，可以在这里实现
        # 目前简单返回成功
        
        return {
            "success": True,
            "message": "登出成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        ChatBILogUtil.error(f"登出失败: {str(e)}")
        return {
            "success": False,
            "message": f"登出失败: {str(e)}"
        }


# 导出
__all__ = ['chatbi_logout']
