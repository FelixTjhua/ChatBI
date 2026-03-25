"""
ChatBI XPack Stub - 本地替代实现
ChatBI 原生实现，无外部依赖
"""
import base64
import hashlib
import os
from enum import Enum
from typing import Optional, List, Any
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# ============== License 管理 ==============
class ChatBILicenseUtil:
    """License 工具类 - 学术版永久有效"""
    
    @staticmethod
    def valid() -> bool:
        """学术版始终返回 True"""
        return True
    
    @staticmethod
    def is_expired() -> bool:
        """学术版永不过期"""
        return False





# ============== Custom Prompt ==============
class CustomPromptTypeEnum(str, Enum):
    """自定义 Prompt 类型枚举"""
    GENERATE_SQL = "generate_sql"
    ANALYSIS = "analysis"
    PREDICT_DATA = "predict_data"


def find_custom_prompts(session: Any, prompt_type: CustomPromptTypeEnum, oid: int, ds_id: Optional[int] = None) -> str:
    """
    查找自定义 Prompt
    学术版返回空字符串，不使用自定义 Prompt 功能
    """
    return ""


# ============== 加密解密 ==============
class SecureEncryption:
    """安全加密类"""
    
    @staticmethod
    def _derive_key(key: str) -> bytes:
        """从字符串密钥派生 32 字节 AES 密钥"""
        return hashlib.sha256(key.encode()).digest()
    
    @staticmethod
    def _derive_iv(key: str) -> bytes:
        """从字符串密钥派生 16 字节 IV"""
        return hashlib.md5(key.encode()).digest()
    
    @staticmethod
    def encrypt_to_single_string(text: str, key: str) -> str:
        """AES-CBC 加密并返回 Base64 编码的字符串"""
        if not text:
            return ""
        try:
            aes_key = SecureEncryption._derive_key(key)
            iv = SecureEncryption._derive_iv(key)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            padded_data = pad(text.encode('utf-8'), AES.block_size)
            encrypted = cipher.encrypt(padded_data)
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"encrypt_to_single_string 失败: {e}")
            raise
    
    @staticmethod
    def decrypt_from_single_string(encrypted_text: str, key: str) -> str:
        """从 Base64 编码的字符串解密"""
        if not encrypted_text:
            return ""
        try:
            aes_key = SecureEncryption._derive_key(key)
            iv = SecureEncryption._derive_iv(key)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            encrypted_data = base64.b64decode(encrypted_text)
            decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            return decrypted.decode('utf-8')
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"decrypt_from_single_string: {e}")
            raise
    
    @staticmethod
    def simple_aes_encrypt(text: str, key: str, iv_text: str) -> str:
        """简单 AES 加密"""
        if not text:
            return ""
        try:
            aes_key = key[:32].ljust(32, '0').encode('utf-8')
            iv = iv_text[:16].ljust(16, '0').encode('utf-8')
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            padded_data = pad(text.encode('utf-8'), AES.block_size)
            encrypted = cipher.encrypt(padded_data)
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"simple_aes_encrypt 失败: {e}")
            raise
    
    @staticmethod
    def simple_aes_decrypt(encrypted_text: str, key: str, iv_text: str) -> str:
        """简单 AES 解密"""
        if not encrypted_text:
            return ""
        try:
            aes_key = key[:32].ljust(32, '0').encode('utf-8')
            iv = iv_text[:16].ljust(16, '0').encode('utf-8')
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            encrypted_data = base64.b64decode(encrypted_text)
            decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
            return decrypted.decode('utf-8')
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"simple_aes_decrypt 失败: {e}")
            raise


def _get_crypto_key() -> str:
    """获取加密密钥：优先使用 CHATBI_CRYPTO_KEY，否则使用 SECRET_KEY"""
    try:
        from common.core.config import settings
        key = settings.CHATBI_CRYPTO_KEY or settings.SECRET_KEY
    except Exception:
        key = os.environ.get('CHATBI_CRYPTO_KEY') or os.environ.get('SECRET_KEY', '')
    if not key:
        import logging
        logging.getLogger(__name__).warning("⚠️ 未配置加密密钥，加密功能不安全")
    return key


async def chatbi_decrypt_impl(text: str) -> str:
    """异步解密实现 — 多层解密策略"""
    if not text:
        return ""
    # 1. 尝试 AES-CBC 解密（后端自身加密的数据）
    key = _get_crypto_key()
    if key:
        try:
            return SecureEncryption.decrypt_from_single_string(text, key)
        except Exception:
            pass
    # 2. 标准 UTF-8 Base64 解码（前端发送的数据）
    try:
        return base64.b64decode(text).decode('utf-8')
    except Exception:
        return text


async def chatbi_encrypt_impl(text: str) -> str:
    """异步加密实现 — 后端敏感数据使用 AES-CBC 加密

    用于加密后端存储的敏感数据（如数据源密码、API Key 等）。
    前端传输层使用 Base64 编码（配合 HTTPS 保护传输安全）。
    """
    if not text:
        return ""
    key = _get_crypto_key()
    if key:
        return SecureEncryption.encrypt_to_single_string(text, key)
    # 无密钥时回退到 Base64（仅用于开发环境）
    import logging
    logging.getLogger(__name__).warning("⚠️ 未配置加密密钥，回退到 Base64 编码（不安全）")
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')


# ============== 文件工具 ==============
class ChatBIFileUtils:
    """文件工具类"""
    
    _upload_dir: str = "/opt/chatbi/data/file"
    
    @classmethod
    def set_upload_dir(cls, path: str):
        """设置上传目录"""
        cls._upload_dir = path
        os.makedirs(path, exist_ok=True)
    
    @classmethod
    def get_file_path(cls, file_id: str) -> str:
        """获取文件路径"""
        return os.path.join(cls._upload_dir, file_id)
    
    @classmethod
    def split_filename_and_flag(cls, filename: str) -> tuple:
        """分割文件名和标志"""
        if '__' in filename:
            parts = filename.rsplit('__', 1)
            if len(parts) == 2:
                flag, name = parts
                return name, flag
        return filename, ''
    
    @classmethod
    def check_file(cls, file: Any, file_types: List[str], limit_file_size: int):
        """检查文件类型和大小"""
        filename = file.filename.lower()
        valid_type = any(filename.endswith(ext) for ext in file_types)
        if not valid_type:
            raise ValueError(
                f"不支持的文件类型，仅支持: {', '.join(file_types)} / "
                f"Unsupported file type, only supported: {', '.join(file_types)}"
            )
    
    @classmethod
    async def upload(cls, file: Any) -> str:
        """上传文件"""
        import uuid
        file_ext = os.path.splitext(file.filename)[1]
        file_id = f"{uuid.uuid4().hex}{file_ext}"
        file_path = cls.get_file_path(file_id)
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return file_id
    
    @classmethod
    def delete_file(cls, file_id: str):
        """删除文件"""
        if file_id:
            file_path = cls.get_file_path(file_id)
            if os.path.exists(file_path):
                os.remove(file_path)


# ============== 权限模型 ==============
class DsPermission:
    """数据源权限模型"""
    id: int
    table_id: int
    type: str  # 'row' or 'column'
    permissions: str  # JSON string


class PermissionDTO:
    """权限 DTO"""
    pass


class DsRules:
    """数据源规则模型"""
    id: int
    permission_list: str  # JSON string
    user_list: str  # JSON string


def transRecord2DTO(session: Any, permission: Any) -> PermissionDTO:
    """转换权限记录为 DTO"""
    return PermissionDTO()


# ============== 认证管理 ==============
async def logout(session: Any, request: Any, dto: Any) -> None:
    """登出处理 - 学术版无需特殊处理"""
    return None


# ============== XPack 核心 ==============
class XPackCore:
    """XPack 核心类"""
    
    @staticmethod
    async def clean_xpack_cache():
        """清理缓存 - 学术版无需处理"""
        pass


def init_fastapi_app(app: Any):
    """初始化 FastAPI 应用 - 学术版无需额外配置"""
    pass


# 创建 core 实例
core = XPackCore()
