from typing import Optional
from common.core.config import settings
from common.chatbi.xpack_stub import SecureEncryption

simple_aes_iv_text = 'chatbi_em_aes_iv'
# ⚠️ 安全说明：simple_aes_encrypt 使用固定 IV，仅用于前端传输加密（如密码字段）。
# 敏感数据持久化加密应使用 chatbi_aes_encrypt（随机 IV，密文自包含）。
def chatbi_aes_encrypt(text: str, key: Optional[str] = None) -> str:
    return SecureEncryption.encrypt_to_single_string(text, key or settings.SECRET_KEY)

def chatbi_aes_decrypt(text: str, key: Optional[str] = None) -> str:
    return SecureEncryption.decrypt_from_single_string(text, key or settings.SECRET_KEY)



def simple_aes_encrypt(text: str, key: Optional[str] = None, ivtext: Optional[str] = None) -> str:
    return SecureEncryption.simple_aes_encrypt(text, key or settings.SECRET_KEY[:32], ivtext or simple_aes_iv_text)

def simple_aes_decrypt(text: str, key: Optional[str] = None, ivtext: Optional[str] = None) -> str:
    return SecureEncryption.simple_aes_decrypt(text, key or settings.SECRET_KEY[:32], ivtext or simple_aes_iv_text)