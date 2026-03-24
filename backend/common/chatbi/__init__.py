"""ChatBI 核心模块"""

# ChatBI 版本信息
__version__ = "1.0.0"
__author__ = "Felix Alvin Juandra (蔡威广)"
__copyright__ = "Copyright © 2025-2026 Felix Alvin Juandra (蔡威广)"

# 导出核心模块
from .core import init_chatbi_app, clean_chatbi_cache
from .crypto import ChatBICrypto, SecureEncryption, chatbi_encrypt, chatbi_decrypt
from .license import ChatBILicenseUtil
from .auth import chatbi_logout
from .file_utils import ChatBIFileUtils
from .permissions import DsRules, DsPermission, PermissionDTO, transRecord2DTO
from .custom_prompt import find_custom_prompts, find_relevant_custom_prompts, count_custom_prompts, CustomPromptTypeEnum

__all__ = [
    # 版本信息
    '__version__',
    '__author__',
    '__copyright__',
    # 核心模块
    'init_chatbi_app',
    'clean_chatbi_cache',
    # 加密模块
    'ChatBICrypto',
    'SecureEncryption',
    'chatbi_encrypt',
    'chatbi_decrypt',
    # License 模块
    'ChatBILicenseUtil',
    # 认证模块
    'chatbi_logout',
    # 文件工具
    'ChatBIFileUtils',
    # 权限模块
    'DsRules',
    'DsPermission',
    'PermissionDTO',
    'transRecord2DTO',
    # 自定义 Prompt
    'find_custom_prompts',
    'find_relevant_custom_prompts',
    'count_custom_prompts',
    'CustomPromptTypeEnum',
]
