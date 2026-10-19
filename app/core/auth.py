"""JWT 鉴权 + 密码哈希 + RBAC（对应 SDD 8.1 / 6.3）。"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)

ROLES = ("operator", "monitor", "manager", "admin")


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 哈希（标准库，避免 passlib/bcrypt 版本兼容坑）。"""
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$")
    except ValueError:
        return False
    return hashlib.pbkdf2_hmac("sha256", plain.encode(), bytes.fromhex(salt), 100_000).hex() == h


def create_token(user_id: str, role: str) -> str:
    s = get_settings()
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    """从 Bearer token 解出当前用户（所有业务接口依赖）。"""
    if creds is None:
        raise HTTPException(status_code=401, detail="未认证")
    try:
        payload = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return {"user_id": payload.get("sub"), "role": payload.get("role", "operator")}


def require_role(*allowed: str):
    """RBAC：限定角色。"""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="无权限")
        return user

    return checker
