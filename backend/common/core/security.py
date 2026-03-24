from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
import hashlib
import logging
from common.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_access_token(data: dict | Any, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _is_bcrypt_hash(hashed: str) -> bool:
    """检查密码是否为bcrypt格式"""
    return hashed.startswith("$2b$") or hashed.startswith("$2a$")


def _md5pwd(password: str) -> str:
    """MD5哈希 - 仅用于兼容旧密码验证，不用于新密码"""
    m = hashlib.md5()
    m.update(password.encode("utf-8"))
    return m.hexdigest()


def hash_password(password: str) -> str:
    """使用bcrypt哈希密码（所有新密码统一使用此函数）"""
    return pwd_context.hash(password)


def verify_pwd(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码 - 兼容bcrypt和旧MD5格式
    如果是MD5格式的旧密码，验证通过后会记录日志提示迁移
    """
    if _is_bcrypt_hash(hashed_password):
        return pwd_context.verify(plain_password, hashed_password)
    # 兼容旧MD5密码
    if _md5pwd(plain_password) == hashed_password:
        logger.warning("检测到MD5格式的旧密码，建议用户修改密码以升级为bcrypt格式")
        return True
    return False


def default_pwd() -> str:
    return settings.DEFAULT_PWD


def default_hashed_pwd() -> str:
    """返回默认密码的bcrypt哈希"""
    return hash_password(default_pwd())


# ===== 向后兼容别名（逐步废弃） =====
def md5pwd(password: str) -> str:
    """已废弃：请使用 hash_password()"""
    logger.warning("md5pwd() 已废弃，请迁移到 hash_password()")
    return hash_password(password)


def verify_md5pwd(plain_password: str, hashed_password: str) -> bool:
    """已废弃：请使用 verify_pwd()"""
    return verify_pwd(plain_password, hashed_password)


def default_md5_pwd() -> str:
    """已废弃：请使用 default_hashed_pwd()"""
    return default_hashed_pwd()