"""登录接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import auth
from app.core.errors import ApiResponse
from app.data import models
from app.data.database import get_read_session

router = APIRouter()


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/auth/login", response_model=ApiResponse)
def login(req: LoginReq) -> ApiResponse:
    with get_read_session() as s:
        u = s.query(models.AppUser).filter_by(username=req.username).first()
    if u is None or not auth.verify_password(req.password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = auth.create_token(u.user_id, u.role)
    return ApiResponse(data={"token": token, "user_id": u.user_id, "role": u.role})
