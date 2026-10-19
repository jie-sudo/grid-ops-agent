"""Agent 运行指标接口（可观测/监控，限 admin）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import auth
from app.core.errors import ApiResponse
from app.data import repository

router = APIRouter()


@router.get("/metrics", response_model=ApiResponse)
def get_metrics(_user: dict = Depends(auth.require_role("admin"))) -> ApiResponse:
    return ApiResponse(data=repository.get_agent_metrics())
