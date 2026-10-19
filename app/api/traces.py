"""追溯查询接口（仅管理员）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


@router.get("/traces/{session_id}", response_model=ApiResponse)
def get_traces(
    session_id: str,
    start: str | None = None,
    end: str | None = None,
    user: dict = Depends(auth.require_role("admin")),
) -> ApiResponse:
    return ApiResponse(data={"session_id": session_id, "traces": repository.get_traces(session_id, start, end)})
