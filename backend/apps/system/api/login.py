from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from apps.system.schemas.logout_schema import LogoutSchema
from apps.system.schemas.system_schema import BaseUserDTO
from apps.system.crud.user import check_account_exists, check_email_exists, check_email_format, check_pwd_format
from apps.system.models.user import UserModel
from common.core.deps import SessionDep, Trans
from common.utils.crypto import chatbi_decrypt
from ..crud.user import authenticate
from common.core.security import create_access_token, hash_password
from datetime import timedelta, datetime
from common.core.config import settings
from common.core.schemas import Token
from common.chatbi.xpack_stub import logout as xpack_logout
from sqlmodel import select
from collections import defaultdict
import time

router = APIRouter(tags=["login"], prefix="/login")

# 注册速率限制：每个IP每分钟最多5次注册尝试
_register_attempts: dict[str, list[float]] = defaultdict(list)
REGISTER_RATE_LIMIT = 5  # 每分钟最大注册次数
REGISTER_RATE_WINDOW = 60  # 时间窗口（秒）

def _check_register_rate_limit(ip: str) -> bool:
    """检查注册速率限制，返回True表示允许注册"""
    now = time.time()
    # 清理过期记录
    _register_attempts[ip] = [t for t in _register_attempts[ip] if now - t < REGISTER_RATE_WINDOW]
    # 检查是否超过限制
    if len(_register_attempts[ip]) >= REGISTER_RATE_LIMIT:
        return False
    # 记录本次尝试
    _register_attempts[ip].append(now)
    
    # 定期清理不活跃 IP 的记录，防止内存泄漏
    # 每 50 次调用清理一次所有过期 IP
    if len(_register_attempts) > 50:
        expired_ips = [k for k, v in _register_attempts.items() if not v or now - max(v) > REGISTER_RATE_WINDOW * 2]
        for k in expired_ips:
            del _register_attempts[k]
    
    return True


class RegisterSchema(BaseModel):
    username: str
    password: str
    email: str
    name: str


@router.post("/access-token")
async def local_login(
    session: SessionDep,
    trans: Trans,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    origin_account = await chatbi_decrypt(form_data.username)
    origin_pwd = await chatbi_decrypt(form_data.password)
    user: BaseUserDTO = authenticate(session=session, account=origin_account, password=origin_pwd)
    if not user:
        raise HTTPException(status_code=400, detail=trans('i18n_login.account_pwd_error'))
    if user.status != 1:
        raise HTTPException(status_code=400, detail=trans('i18n_login.user_disable', msg = trans('i18n_concat_admin')))
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    user_dict = user.to_dict()
    return Token(access_token=create_access_token(
        user_dict, expires_delta=access_token_expires
    ))


@router.post("/register")
async def register(
    session: SessionDep,
    trans: Trans,
    request: Request,
    data: RegisterSchema
):
    """用户注册 - 带速率限制"""
    # 获取客户端IP
    client_ip = request.client.host if request.client else "unknown"
    
    # 检查速率限制
    if not _check_register_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail=trans('i18n_register.rate_limit_exceeded'))
    
    # 解密数据
    username = await chatbi_decrypt(data.username)
    password = await chatbi_decrypt(data.password)
    email = await chatbi_decrypt(data.email)
    name = await chatbi_decrypt(data.name)
    
    # 验证账号是否已存在
    if check_account_exists(session=session, account=username):
        raise HTTPException(status_code=400, detail=trans('i18n_register.account_exists'))
    
    # 验证邮箱是否已存在
    if check_email_exists(session=session, email=email):
        raise HTTPException(status_code=400, detail=trans('i18n_register.email_exists'))
    
    # 验证邮箱格式
    if not check_email_format(email):
        raise HTTPException(status_code=400, detail=trans('i18n_register.email_invalid'))
    
    # 验证密码格式
    if not check_pwd_format(password):
        raise HTTPException(status_code=400, detail=trans('i18n_register.pwd_invalid'))
    
    # 验证用户名长度和格式，防止超长用户名或特殊字符
    if not username or len(username) < 2 or len(username) > 50:
        raise HTTPException(status_code=400, detail=trans('i18n_register.account_invalid'))
    if not name or len(name) < 1 or len(name) > 50:
        raise HTTPException(status_code=400, detail=trans('i18n_register.name_invalid'))
    
    # 创建用户
    # 显式设置 oid=1（默认工作空间），防止新用户因 oid 为 NULL 导致数据隔离失效
    user_model = UserModel(
        account=username,
        password=hash_password(password),
        email=email,
        name=name,
        language="zh-CN",
        status=1,
        role="member",
        oid=1
    )
    session.add(user_model)
    session.commit()
    
    return {"message": trans('i18n_register.success')}


@router.post("/logout")    
async def logout(session: SessionDep, request: Request, dto: LogoutSchema):
    if dto.origin != 0:
        return await xpack_logout(session, request, dto)
    return None