import hashlib
import logging
import os

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import base64

logger = logging.getLogger(__name__)

# 从环境变量获取密钥，回退到settings.SECRET_KEY
def _get_ds_key() -> bytes:
    """获取数据源加密密钥（16字节）"""
    env_key = os.environ.get("CHATBI_CRYPTO_KEY", "")
    if env_key:
        return hashlib.md5(env_key.encode()).digest()
    try:
        from common.core.config import settings
        return hashlib.md5(settings.SECRET_KEY.encode()).digest()
    except Exception:
        return hashlib.md5(b"chatbi_default_key").digest()

# 前端 CryptoJS.enc.Utf8.parse('ChatBI1234567890') = 16字节标准 AES-128 密钥
_LEGACY_KEY = b'ChatBI1234567890'


def aes_encrypt(data):
    """AES-CBC加密（使用配置密钥 + 随机IV）
    
     从 ECB 模式升级为 CBC 模式。
    ECB 模式对相同明文产生相同密文，存在模式泄漏风险。
    CBC 模式使用随机 IV，相同明文每次加密结果不同，更安全。
    输出格式：base64(IV + ciphertext)
    """
    key = _get_ds_key()
    data = bytes(data, 'utf-8')
    iv = os.urandom(AES.block_size)  # 16字节随机IV
    cipher = AES.new(key, AES.MODE_CBC, iv)
    data = pad(data, AES.block_size)
    encrypt = cipher.encrypt(data)
    # IV 拼接在密文前面，解密时取前16字节作为IV
    return base64.b64encode(iv + encrypt)


def aes_decrypt(encrypted_data):
    """AES解密（兼容 CBC 新格式 + ECB 旧格式 + 旧密钥）
    
     解密时自动检测格式：
    1. 先尝试 CBC 模式（新密钥）：前16字节为IV
    2. 回退 ECB 模式（新密钥）：兼容升级前加密的数据
    3. 回退 ECB 模式（旧密钥）：兼容最早期的数据
    """
    key = _get_ds_key()
    encrypted_bytes = base64.b64decode(encrypted_data)
    
    # 1. 尝试 CBC 模式（新格式：IV + ciphertext）
    if len(encrypted_bytes) > AES.block_size:
        try:
            iv = encrypted_bytes[:AES.block_size]
            ciphertext = encrypted_bytes[AES.block_size:]
            cipher = AES.new(key, AES.MODE_CBC, iv)
            text = cipher.decrypt(ciphertext)
            decrypted_text = unpad(text, AES.block_size)
            return decrypted_text.decode('utf-8')
        except Exception:
            pass
    
    # 2. 回退 ECB 模式（新密钥，兼容升级前的数据）
    try:
        cipher = AES.new(key, AES.MODE_ECB)
        text = cipher.decrypt(encrypted_bytes)
        decrypted_text = unpad(text, AES.block_size)
        logger.info("使用ECB模式解密成功，建议重新加密以升级为CBC模式")
        return decrypted_text.decode('utf-8')
    except Exception:
        pass
    
    # 3. 回退旧密钥 ECB 模式（兼容最早期数据）
    try:
        cipher = AES.new(_LEGACY_KEY, AES.MODE_ECB)
        text = cipher.decrypt(encrypted_bytes)
        decrypted_text = unpad(text, AES.block_size)
        logger.warning("使用旧密钥解密数据源配置成功，建议重新加密以使用新密钥和CBC模式")
        return decrypted_text.decode('utf-8')
    except Exception:
        pass
    
    # 4. 回退 CryptoJS 15字节旧密钥 ECB 模式
    try:
        _LEGACY_KEY_15 = b'ChatBI123456789\x00'
        cipher = AES.new(_LEGACY_KEY_15, AES.MODE_ECB)
        text = cipher.decrypt(encrypted_bytes)
        decrypted_text = unpad(text, AES.block_size)
        logger.warning("使用CryptoJS 15字节旧密钥解密成功，建议重新加密")
        return decrypted_text.decode('utf-8')
    except Exception as e:
        logger.error(f"数据源配置解密失败: {e}")
        raise
