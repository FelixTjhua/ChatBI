"""ChatBI 核心初始化模块"""

from typing import Any
from fastapi import FastAPI

from common.utils.utils import ChatBILogUtil


def init_chatbi_app(app: FastAPI) -> FastAPI:
    """初始化 ChatBI FastAPI 应用"""
    ChatBILogUtil.info("🚀 ChatBI 核心模块初始化中...")
    
    # 添加 ChatBI 元数据
    app.title = "ChatBI - 基于RAG与大语言模型的商业智能分析对话系统"
    app.description = """
    ChatBI - Business Intelligence Analysis Dialogue System based on RAG and LLM
    
    Copyright © 2025-2026 Felix Alvin Juandra (蔡威广)
    
    毕业论文项目 - 基于RAG与大语言模型的商业智能分析对话系统
    """
    app.version = "1.0.0"
    
    # 添加自定义状态
    app.state.chatbi_initialized = True
    app.state.chatbi_version = "1.0.0"
    
    ChatBILogUtil.info("ChatBI 核心模块初始化完成")
    
    return app


async def clean_chatbi_cache() -> None:
    """
    清理 ChatBI 缓存
    
    在应用启动时调用，清理可能存在的旧缓存数据
    """
    try:
        ChatBILogUtil.info("🧹 清理 ChatBI 缓存...")
        
        # 这里可以添加具体的缓存清理逻辑
        # 例如清理 Redis 缓存、文件缓存等
        
        # 目前简单记录日志
        ChatBILogUtil.info("ChatBI 缓存清理完成")
        
    except Exception as e:
        ChatBILogUtil.warning(f"缓存清理时出现警告: {str(e)}")


# 导出
__all__ = ['init_chatbi_app', 'clean_chatbi_cache']
