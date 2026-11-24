"""认证域入参/出参模型"""

from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    account: str = Field(min_length=2, max_length=64, description='登录账号')
    password: str = Field(min_length=1, max_length=512, description='RSA加密后的密码密文（base64），明文长度由解密层校验')


class LoginRequest(BaseModel):
    account: str = Field(min_length=1, max_length=64, description='登录账号')
    password: str = Field(min_length=1, max_length=512, description='RSA加密后的密码密文（base64）')
    device_id: Optional[str] = Field(default=None, max_length=64, description='设备标识，多端登录时区分会话')


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = Field(default=None, max_length=512, description='RT；Web端从HttpOnly Cookie读取，App端从body传入')


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=512, description='RSA加密后的原密码密文（base64）')
    new_password: str = Field(min_length=1, max_length=512, description='RSA加密后的新密码密文（base64），明文长度由解密层校验')


class UserInfo(BaseModel):
    id: str
    account: str
    created_at: Optional[str] = None


class TokenBundle(BaseModel):
    """签发的令牌组：AT走body，RT由接口层按端写入Cookie或body"""
    access_token: str
    expires_in: int
    token_type: str = 'Bearer'
    refresh_token: Optional[str] = None
    user: Optional[UserInfo] = None
