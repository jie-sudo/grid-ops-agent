"""历史消息查询接口（审计回看，限 manager/admin）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


@router.get("/messages", response_model=ApiResponse)
def list_messages(
    session_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: dict = Depends(auth.require_role("manager", "admin")),
) -> ApiResponse:
    """历史消息（按会话/时间/分页）。"""
    messages = repository.list_messages(session_id, start, end, limit, offset)
    return ApiResponse(data={"messages": messages, "count": len(messages)})
