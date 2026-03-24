
from typing import Optional
from sqlmodel import Session, func, select, delete as sqlmodel_delete
from apps.system.schemas.auth import CacheName, CacheNamespace
from apps.system.schemas.system_schema import EMAIL_REGEX, PWD_REGEX, BaseUserDTO, UserInfoDTO
from common.core.deps import SessionDep
from common.core.chatbi_cache import cache, clear_cache
from common.utils.utils import ChatBILogUtil
from ..models.user import UserModel
from common.core.security import verify_pwd, hash_password, _is_bcrypt_hash
import re
import logging

logger = logging.getLogger(__name__)

def get_db_user(*, session: Session, user_id: int) -> UserModel:
    db_user = session.get(UserModel, user_id)
    return db_user

def get_user_by_account(*, session: Session, account: str) -> BaseUserDTO | None:
    statement = select(UserModel).where(UserModel.account == account)
    db_user = session.exec(statement).first()
    if not db_user:
        return None
    return BaseUserDTO.model_validate(db_user.model_dump())

@cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="user_id")
async def get_user_info(*, session: Session, user_id: int) -> UserInfoDTO | None:
    db_user: UserModel = get_db_user(session = session, user_id = user_id)
    if not db_user:
        return None
    userInfo = UserInfoDTO.model_validate(db_user.model_dump())
    # 基于role字段判断是否为管理员
    userInfo.isAdmin = userInfo.role == 'admin'
    return userInfo

def authenticate(*, session: Session, account: str, password: str) -> BaseUserDTO | None:
    db_user = get_user_by_account(session=session, account=account)
    if not db_user:
        return None
    if not verify_pwd(password, db_user.password):
        return None
    # 自动升级：如果用户仍使用MD5密码，登录成功后自动升级为bcrypt
    if not _is_bcrypt_hash(db_user.password):
        try:
            db_model = session.get(UserModel, db_user.id)
            if db_model:
                db_model.password = hash_password(password)
                session.add(db_model)
                session.commit()
                logger.info(f"用户 {account} 的密码已自动从MD5升级为bcrypt")
        except Exception as e:
            logger.warning(f"自动升级密码失败: {e}")
    return db_user


    
@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="id")
async def single_delete(session: SessionDep, id: int):
    user_model: UserModel = get_db_user(session = session, user_id = id)
    session.delete(user_model)
    session.commit()

@clear_cache(namespace=CacheNamespace.AUTH_INFO, cacheName=CacheName.USER_INFO, keyExpression="id")    
async def clean_user_cache(id: int):
    ChatBILogUtil.info(f"User cache for [{id}] has been cleaned")


def check_account_exists(*, session: Session, account: str) -> bool:
    return session.exec(select(func.count()).select_from(UserModel).where(UserModel.account == account)).one() > 0
def check_email_exists(*, session: Session, email: str) -> bool:
    return session.exec(select(func.count()).select_from(UserModel).where(UserModel.email == email)).one() > 0



def check_email_format(email: str) -> bool:
    return bool(EMAIL_REGEX.fullmatch(email))

def check_pwd_format(pwd: str) -> bool:
    return bool(PWD_REGEX.fullmatch(pwd))
