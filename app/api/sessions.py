"""会话列表接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


@router.get("/sessions", response_model=ApiResponse)
def list_sessions(
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(auth.get_current_user),
) -> ApiResponse:
    """当前用户的历史会话列表（按时间/分页）。"""
    sessions = repository.list_sessions(user["user_id"], start, end, limit, offset)
    return ApiResponse(data={"sessions": sessions, "count": len(sessions)})
