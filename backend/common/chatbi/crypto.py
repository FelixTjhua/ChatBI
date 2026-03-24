"""ChatBI 加密解密模块"""

import base64
import hashlib
import os
import logging
from typing import Optional

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger(__name__)


class ChatBICrypto:
    """ChatBI 加密解密工具类"""
    
    @staticmethod
    def _get_default_key() -> str:
        """从环境变量获取默认密钥，避免硬编码"""
        return os.environ.get("CHATBI_CRYPTO_KEY", "") or _get_settings_key()
    
    @staticmethod
    def _get_key(key: Optional[str] = None) -> bytes:
        """获取32字节的密钥"""
        key_str = key or ChatBICrypto._get_default_key()
        if not key_str:
            raise ValueError(
                "加密密钥未配置，请设置 CHATBI_CRYPTO_KEY 环境变量或 SECRET_KEY / "
                "Encryption key not configured. Please set CHATBI_CRYPTO_KEY env variable or SECRET_KEY"
            )
        # 使用SHA256确保密钥长度为32字节
        return hashlib.sha256(key_str.encode()).digest()
    
    @staticmethod
    def _generate_iv() -> bytes:
        """生成随机16字节IV"""
        return os.urandom(16)
    
    @classmethod
    def encrypt(cls, plaintext: str, key: Optional[str] = None) -> str:
        """AES加密（随机IV，IV前置于密文中）"""
        if not plaintext:
            return plaintext
            
        try:
            key_bytes = cls._get_key(key)
            iv = cls._generate_iv()
            
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
            padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
            encrypted = cipher.encrypt(padded_data)
            
            # IV前置于密文，解密时提取
            return base64.b64encode(iv + encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {type(e).__name__}: {e}")
            raise
    
    @classmethod
    def decrypt(cls, ciphertext: str, key: Optional[str] = None) -> str:
        """AES解密（从密文中提取IV）"""
        if not ciphertext:
            return ciphertext
            
        try:
            key_bytes = cls._get_key(key)
            raw = base64.b64decode(ciphertext)
            
            if len(raw) <= 16:
                # 尝试旧格式兼容（固定IV）
                return cls._decrypt_legacy(ciphertext, key)
            
            # 新格式：前16字节为IV
            iv = raw[:16]
            encrypted = raw[16:]
            
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            
            return decrypted.decode('utf-8')
        except Exception:
            # 尝试旧格式兼容
            try:
                return cls._decrypt_legacy(ciphertext, key)
            except Exception as e:
                logger.error(f"解密失败: {type(e).__name__}: {e}")
                raise
    
    @classmethod
    def _decrypt_legacy(cls, ciphertext: str, key: Optional[str] = None) -> str:
        """兼容旧版固定IV格式的解密"""
        key_bytes = cls._get_key(key)
        iv = b'chatbi_iv_16byt'
        
        encrypted = base64.b64decode(ciphertext)
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
        
        return decrypted.decode('utf-8')


class SecureEncryption:
    """安全加密类 - 兼容接口"""
    
    @staticmethod
    def encrypt_to_single_string(text: str, key: str) -> str:
        """加密为单个字符串"""
        return ChatBICrypto.encrypt(text, key)
    
    @staticmethod
    def decrypt_from_single_string(text: str, key: str) -> str:
        """从单个字符串解密"""
        return ChatBICrypto.decrypt(text, key)
    
    @staticmethod
    def simple_aes_encrypt(text: str, key: str, iv_text: str) -> str:
        """简单AES加密（使用指定IV）"""
        try:
            key_bytes = key.encode('utf-8')[:32].ljust(32, b'\0')
            iv_bytes = iv_text.encode('utf-8')[:16].ljust(16, b'\0')
            
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            padded_data = pad(text.encode('utf-8'), AES.block_size)
            encrypted = cipher.encrypt(padded_data)
            
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"simple_aes_encrypt 失败: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    def simple_aes_decrypt(text: str, key: str, iv_text: str) -> str:
        """简单AES解密"""
        try:
            key_bytes = key.encode('utf-8')[:32].ljust(32, b'\0')
            iv_bytes = iv_text.encode('utf-8')[:16].ljust(16, b'\0')
            
            encrypted = base64.b64decode(text)
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"simple_aes_decrypt 失败: {type(e).__name__}: {e}")
            raise


def _get_settings_key() -> str:
    """延迟导入settings以避免循环依赖"""
    try:
        from common.core.config import settings
        return settings.SECRET_KEY
    except Exception:
        return ""


# 异步版本的加密解密函数
async def chatbi_encrypt(text: str) -> str:
    """异步加密函数"""
    return ChatBICrypto.encrypt(text)


async def chatbi_decrypt(text: str) -> str:
    """异步解密函数"""
    return ChatBICrypto.decrypt(text)
